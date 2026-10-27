"""Expedia Rapid lodging search adapter.

Rapid requires an approved partner account. No credentials or inventory are
embedded in the application; the adapter is inert until configured.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


RAPID_TEST_BASE_URL = "https://test.ean.com/v3/"
RAPID_PRODUCTION_BASE_URL = "https://api.ean.com/v3/"
RAPID_DOCS = "https://developers.expediagroup.com/rapid/lodging"


class HotelProviderError(Exception):
    """Sanitized provider operation failure."""


class HotelProviderNotConfigured(HotelProviderError):
    pass


class HotelProviderRateLimited(HotelProviderError):
    pass


class HotelProviderUnavailable(HotelProviderError):
    pass


def validate_stay(check_in: str, check_out: str) -> tuple[date, date]:
    try:
        start = date.fromisoformat(check_in)
        end = date.fromisoformat(check_out)
    except (TypeError, ValueError) as error:
        raise ValueError("Check-in and check-out must be valid ISO dates (YYYY-MM-DD).") from error
    today = date.today()
    if start < today or end <= start:
        raise ValueError("Check-in must be today or later and check-out must be after check-in.")
    if (end - start).days > 28:
        raise ValueError("Hotel stays may not exceed 28 nights.")
    return start, end


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 and parsed != float("inf") and parsed == parsed else None


def _token_from_link(link: str) -> str:
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(link).query).get("token", [""])[0]


def _normalize_name(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _offer_total(rate: dict[str, Any]) -> tuple[float | None, str | None]:
    pricing = rate.get("occupancy_pricing")
    if not isinstance(pricing, dict) or not pricing:
        return None, None
    for data in pricing.values():
        totals = data.get("totals", {}) if isinstance(data, dict) else {}
        inclusive = totals.get("inclusive", {}) if isinstance(totals, dict) else {}
        amount = inclusive.get("request_currency") or inclusive.get("billable_currency")
        if isinstance(amount, dict):
            return _number(amount.get("value")), amount.get("currency")
    return None, None


class ExpediaRapidClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        shared_secret: str | None = None,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key or os.environ.get("EXPEDIA_RAPID_API_KEY", "")
        self.shared_secret = shared_secret or os.environ.get("EXPEDIA_RAPID_SHARED_SECRET", "")
        self.base_url = (
            base_url
            or os.environ.get("EXPEDIA_RAPID_BASE_URL")
            or RAPID_TEST_BASE_URL
        ).rstrip("/") + "/"
        self._http_client = http_client

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.shared_secret)

    def _headers(self, session_id: str | None = None, customer_ip: str | None = None) -> dict[str, str]:
        if not self.configured:
            raise HotelProviderNotConfigured(
                "Expedia Rapid is not configured. Approved partner API credentials are required."
            )
        timestamp = str(int(time.time()))
        signature = hashlib.sha512(
            f"{self.api_key}{self.shared_secret}{timestamp}".encode("utf-8")
        ).hexdigest()
        headers = {
            "Authorization": (
                f"EAN APIKey={self.api_key},Signature={signature},timestamp={timestamp}"
            ),
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": "WanderWise/1.0",
        }
        if session_id:
            headers["Customer-Session-Id"] = session_id
        if customer_ip:
            headers["Customer-Ip"] = customer_ip
        return headers

    async def aclose(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: list[tuple[str, str]] | dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        session_id: str | None = None,
        customer_ip: str | None = None,
    ) -> httpx.Response:
        target_url = urljoin(self.base_url, path_or_url)
        parsed = urlparse(target_url)
        if parsed.scheme != "https" or parsed.netloc != urlparse(self.base_url).netloc:
            raise HotelProviderError("The provider returned an unsupported API link.")

        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(12.0, connect=5.0),
                follow_redirects=False,
            )
        client = self._http_client
        for attempt in range(2):
            try:
                response = await client.request(
                    method,
                    target_url,
                    params=params,
                    json=json_body,
                    headers=self._headers(session_id, customer_ip),
                )
            except httpx.TimeoutException as error:
                if attempt == 0 and method.upper() == "GET":
                    continue
                raise HotelProviderUnavailable(
                    "The hotel provider did not respond in time."
                ) from error
            except httpx.RequestError as error:
                raise HotelProviderUnavailable(
                    "The hotel provider could not be reached."
                ) from error
            if response.status_code == 429:
                raise HotelProviderRateLimited(
                    "The hotel provider is rate limiting requests. Please try again later."
                )
            if response.status_code in {502, 503, 504} and attempt == 0 and method.upper() == "GET":
                continue
            if response.status_code in {401, 403}:
                raise HotelProviderNotConfigured(
                    "Expedia Rapid rejected these credentials or this API permission."
                )
            if response.status_code >= 400:
                raise HotelProviderUnavailable(
                    f"Expedia Rapid returned an error (HTTP {response.status_code})."
                )
            return response
        raise HotelProviderUnavailable("The hotel provider is temporarily unavailable.")

    async def _get_json(
        self,
        path: str,
        *,
        params: list[tuple[str, str]] | dict[str, Any] | None = None,
        session_id: str | None = None,
        customer_ip: str | None = None,
    ) -> tuple[Any, httpx.Response]:
        response = await self._request(
            "GET",
            path,
            params=params,
            session_id=session_id,
            customer_ip=customer_ip,
        )
        try:
            return response.json(), response
        except ValueError as error:
            raise HotelProviderError("Expedia Rapid returned malformed JSON.") from error

    async def resolve_region(self, destination: str, session_id: str | None = None) -> dict[str, Any]:
        """Resolve by paging Expedia's official region catalog, then exact local match."""
        url = "regions"
        params: list[tuple[str, str]] | None = [
            ("country_code", "IN"),
            ("type", "city"),
            ("include", "standard"),
            ("language", "en-US"),
            ("limit", "1000"),
        ]
        target = _normalize_name(destination)
        regions: list[dict[str, Any]] = []
        for _ in range(10):
            payload, response = await self._get_json(
                url, params=params, session_id=session_id
            )
            if not isinstance(payload, list):
                raise HotelProviderError("Expedia Rapid returned an invalid region catalog.")
            regions.extend(region for region in payload if isinstance(region, dict))
            next_link = response.links.get("next")
            if not next_link:
                break
            url = next_link.get("url", "")
            params = None
        else:
            raise HotelProviderError("The provider region catalog exceeded the supported page limit.")

        matches = [
            region for region in regions
            if region.get("country_code") == "IN"
            and _normalize_name(str(region.get("name", ""))) == target
        ]
        if not matches:
            raise LookupError("No matching Expedia Rapid hotel-search region was found.")
        matches.sort(key=lambda region: (region.get("type") != "city", str(region.get("id", ""))))
        return matches[0]

    async def search(
        self,
        *,
        destination: str,
        check_in: str,
        check_out: str,
        adults: int,
        rooms: int,
        child_ages: list[int],
        currency: str,
        session_id: str,
        customer_ip: str | None = None,
    ) -> dict[str, Any]:
        try:
            return await self._search(
                destination=destination,
                check_in=check_in,
                check_out=check_out,
                adults=adults,
                rooms=rooms,
                child_ages=child_ages,
                currency=currency,
                session_id=session_id,
                customer_ip=customer_ip,
            )
        finally:
            await self.aclose()

    async def _search(
        self,
        *,
        destination: str,
        check_in: str,
        check_out: str,
        adults: int,
        rooms: int,
        child_ages: list[int],
        currency: str,
        session_id: str,
        customer_ip: str | None = None,
    ) -> dict[str, Any]:
        start, end = validate_stay(check_in, check_out)
        if not 1 <= adults <= 16 or not 1 <= rooms <= 8:
            raise ValueError("Adults must be 1-16 and rooms must be 1-8.")
        if len(child_ages) > 16 or any(not 0 <= age <= 17 for age in child_ages):
            raise ValueError("Child ages must be between 0 and 17.")
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("Currency must be an ISO 4217 three-letter code.")

        region = await self.resolve_region(destination, session_id)
        region_id = str(region.get("id", ""))
        if not region_id:
            raise HotelProviderError("The provider region result did not contain an identifier.")
        details, _ = await self._get_json(
            f"regions/{region_id}",
            params=[
                ("include", "details"),
                ("include", "property_ids"),
                ("language", "en-US"),
            ],
            session_id=session_id,
        )
        property_ids = details.get("property_ids", []) if isinstance(details, dict) else []
        property_ids = [str(value) for value in property_ids[:250] if value]
        if not property_ids:
            return {
                "provider": "expedia_rapid",
                "status": "no_results",
                "destination": region.get("name"),
                "region_id": region_id,
                "offers": [],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }

        base_adults, remaining = divmod(adults, rooms)
        if base_adults == 0:
            raise ValueError("There must be at least one adult per room.")
        occupancy = []
        for room_index in range(rooms):
            room_adults = base_adults + (1 if room_index < remaining else 0)
            ages = child_ages if room_index == 0 else []
            occupancy.append(f"{room_adults}" + (f"-{','.join(map(str, ages))}" if ages else ""))
        query = [
            ("checkin", start.isoformat()),
            ("checkout", end.isoformat()),
            ("currency", currency),
            ("country_code", "IN"),
            ("language", "en-US"),
            ("rate_plan_count", "5"),
            ("sales_channel", "website"),
            ("sales_environment", "hotel_only"),
            ("include", "rooms.rates.current_refundability"),
        ]
        query.extend(("occupancy", value) for value in occupancy)
        query.extend(("property_id", value) for value in property_ids)
        availability, _ = await self._get_json(
            "properties/availability",
            params=query,
            session_id=session_id,
            customer_ip=customer_ip,
        )
        if not isinstance(availability, list):
            raise HotelProviderError("Expedia Rapid returned an invalid availability response.")
        content, _ = await self._get_json(
            "properties/content",
            params=[
                *[("property_id", value) for value in property_ids],
                ("language", "en-US"),
                ("supply_source", "expedia"),
                ("include", "address"),
                ("include", "location"),
                ("include", "images"),
            ],
            session_id=session_id,
        )
        content_map = content if isinstance(content, dict) else {}
        retrieved_at = datetime.now(timezone.utc).isoformat()
        offers = []
        for property_result in availability:
            if not isinstance(property_result, dict) or property_result.get("status") != "available":
                continue
            property_id = str(property_result.get("property_id", ""))
            property_data = content_map.get(property_id, {})
            if not isinstance(property_data, dict):
                property_data = {}
            location = property_data.get("location") or {}
            if not isinstance(location, dict):
                location = {}
            coordinates = location.get(
                "coordinates" if not location.get("obfuscation_required") else "obfuscated_coordinates",
                {},
            )
            if not isinstance(coordinates, dict):
                coordinates = {}
            address = property_data.get("address") or {}
            if not isinstance(address, dict):
                address = {}
            if address.get("obfuscation_required"):
                address = {
                    key: address.get(key)
                    for key in ("city", "state_province_name", "country_code")
                    if address.get(key)
                }
            for room in property_result.get("rooms", []):
                if not isinstance(room, dict):
                    continue
                for rate in room.get("rates", []):
                    if not isinstance(rate, dict):
                        continue
                    total, rate_currency = _offer_total(rate)
                    bed_groups = rate.get("bed_groups") or {}
                    price_check_link = None
                    for bed_group in bed_groups.values() if isinstance(bed_groups, dict) else []:
                        candidate = ((bed_group or {}).get("links") or {}).get("price_check")
                        if candidate and candidate.get("href"):
                            price_check_link = candidate
                            break
                    if total is None or not rate_currency or not price_check_link:
                        continue
                    path = str(price_check_link["href"])
                    if urlparse(path).netloc and urlparse(path).netloc != urlparse(self.base_url).netloc:
                        continue
                    offers.append({
                        "provider": "expedia_rapid",
                        "property_id": property_id,
                        "room_id": str(room.get("id", "")),
                        "rate_id": str(rate.get("id", "")),
                        "hotel_name": property_data.get("name"),
                        "address": address,
                        "latitude": coordinates.get("latitude"),
                        "longitude": coordinates.get("longitude"),
                        "images": [
                            image_url
                            for image in property_data.get("images", [])
                            if isinstance(image, dict)
                            for image_url in [
                                (((image.get("links") or {}).get("1000px") or {}).get("href"))
                                or (((image.get("links") or {}).get("350px") or {}).get("href"))
                            ]
                            if image_url
                        ],
                        "room_name": room.get("room_name"),
                        "total_price": total,
                        "currency": rate_currency,
                        "price_breakdown": (rate.get("occupancy_pricing") or {}),
                        "check_in": start.isoformat(),
                        "check_out": end.isoformat(),
                        "occupancy": {"adults": adults, "children_ages": child_ages, "rooms": rooms},
                        "refundable": rate.get("refundable"),
                        "cancellation_penalties": rate.get("cancel_penalties"),
                        "availability": "available",
                        "retrieved_at": retrieved_at,
                        "offer_expires_at": price_check_link.get("expires"),
                        "source": "Expedia Rapid live availability",
                        "_price_check_path": path,
                    })
        return {
            "provider": "expedia_rapid",
            "status": "available" if offers else "no_results",
            "destination": region.get("name"),
            "region_id": region_id,
            "offers": offers,
            "retrieved_at": retrieved_at,
        }

    async def price_check(
        self, path: str, *, session_id: str, customer_ip: str | None = None
    ) -> dict[str, Any]:
        try:
            payload, _ = await self._get_json(
                path, session_id=session_id, customer_ip=customer_ip
            )
            if not isinstance(payload, dict) or payload.get("status") not in {
                "available", "price_changed", "sold_out"
            }:
                raise HotelProviderError("Expedia Rapid returned an invalid price-check response.")
            return payload
        finally:
            await self.aclose()


def hotel_mode() -> str:
    mode = os.environ.get("WANDERWISE_HOTEL_MODE", "demo").strip().casefold()
    if mode not in {"demo", "live", "disabled"}:
        raise ValueError("WANDERWISE_HOTEL_MODE must be demo, live, or disabled.")
    return mode


def build_provider() -> ExpediaRapidClient:
    return ExpediaRapidClient()
