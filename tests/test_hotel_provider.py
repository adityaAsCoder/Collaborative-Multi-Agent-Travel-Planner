import asyncio
import hashlib
from datetime import date, timedelta

import httpx
import pytest

from app.agents.cost_estimator import load_demo_hotels
from app.providers.hotels import (
    ExpediaRapidClient,
    HotelProviderNotConfigured,
    HotelProviderRateLimited,
    hotel_mode,
    validate_stay,
)


def test_demo_mode_is_default_and_properties_are_labeled_synthetic(monkeypatch):
    monkeypatch.delenv("WANDERWISE_HOTEL_MODE", raising=False)
    assert hotel_mode() == "demo"
    hotels = load_demo_hotels("Goa", "Goa", 15.49, 73.82)
    assert hotels
    assert all(
        hotel["data_status"] == "DEMO_SYNTHETIC"
        and hotel["source_type"] == "synthetic"
        and "not a real property address" in hotel["address"]
        for hotel in hotels
    )


def test_hotel_mode_rejects_unknown_configuration(monkeypatch):
    monkeypatch.setenv("WANDERWISE_HOTEL_MODE", "anything")
    with pytest.raises(ValueError):
        hotel_mode()


def _client(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return ExpediaRapidClient(
        api_key="test-key",
        shared_secret="test-secret",
        http_client=http_client,
    )


def _future_stay():
    check_in = date.today() + timedelta(days=30)
    check_out = check_in + timedelta(days=2)
    return check_in.isoformat(), check_out.isoformat()


def test_rapid_auth_header_uses_documented_signature_format():
    client = ExpediaRapidClient(api_key="key", shared_secret="secret")
    headers = client._headers()
    timestamp = headers["Authorization"].split("timestamp=", 1)[1]
    signature = hashlib.sha512(f"keysecret{timestamp}".encode()).hexdigest()
    assert headers["Authorization"] == (
        f"EAN APIKey=key,Signature={signature},timestamp={timestamp}"
    )


def test_rapid_search_normalizes_live_property_offer_and_availability():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/regions"):
            return httpx.Response(200, json=[{
                "id": "city-123",
                "name": "Jaipur",
                "type": "city",
                "country_code": "IN",
            }])
        if request.url.path.endswith("/regions/city-123"):
            return httpx.Response(200, json={"property_ids": ["hotel-1"]})
        if request.url.path.endswith("/properties/availability"):
            return httpx.Response(200, json=[{
                "property_id": "hotel-1",
                "status": "available",
                "rooms": [{
                    "id": "room-1",
                    "room_name": "Queen room",
                    "rates": [{
                        "id": "rate-1",
                        "refundable": True,
                        "cancel_penalties": [],
                        "bed_groups": {
                            "bed-1": {
                                "links": {
                                    "price_check": {
                                        "href": "/v3/properties/hotel-1/rooms/room-1/rates/rate-1?token=short",
                                        "expires": "2030-01-01T00:00:00Z",
                                    }
                                }
                            }
                        },
                        "occupancy_pricing": {
                            "2": {
                                "totals": {
                                    "inclusive": {
                                        "request_currency": {"value": "5000.00", "currency": "INR"}
                                    }
                                }
                            }
                        },
                    }],
                }],
            }])
        if request.url.path.endswith("/properties/content"):
            return httpx.Response(200, json={
                "hotel-1": {
                    "name": "Real Provider Hotel",
                    "address": {
                        "line_1": "1 Sample Road",
                        "city": "Jaipur",
                        "country_code": "IN",
                        "obfuscation_required": False,
                    },
                    "location": {
                        "coordinates": {"latitude": 26.9, "longitude": 75.8},
                    },
                    "images": [],
                }
            })
        raise AssertionError(f"Unexpected provider request {request.url}")

    check_in, check_out = _future_stay()
    result = asyncio.run(_client(handler).search(
        destination="Jaipur",
        check_in=check_in,
        check_out=check_out,
        adults=2,
        rooms=1,
        child_ages=[],
        currency="INR",
        session_id="test-session",
    ))

    assert result["status"] == "available"
    offer = result["offers"][0]
    assert offer["hotel_name"] == "Real Provider Hotel"
    assert offer["total_price"] == 5000
    assert offer["currency"] == "INR"
    assert offer["latitude"] == 26.9
    assert offer["source"] == "Expedia Rapid live availability"
    assert offer["_price_check_path"].endswith("token=short")
    assert any("occupancy=2" in str(call.url) for call in calls)
    assert len(calls) == 4


def test_rapid_search_honors_address_and_coordinate_obfuscation():
    def handler(request):
        if request.url.path.endswith("/regions"):
            return httpx.Response(200, json=[{
                "id": "region",
                "name": "Jaipur",
                "type": "city",
                "country_code": "IN",
            }])
        if request.url.path.endswith("/regions/region"):
            return httpx.Response(200, json={"property_ids": ["hotel"]})
        if request.url.path.endswith("/properties/availability"):
            return httpx.Response(200, json=[{
                "property_id": "hotel",
                "status": "available",
                "rooms": [{
                    "id": "room",
                    "rates": [{
                        "id": "rate",
                        "bed_groups": {"bed": {"links": {"price_check": {"href": "/v3/x?token=t"}}}},
                        "occupancy_pricing": {"2": {"totals": {"inclusive": {"request_currency": {"value": "200", "currency": "INR"}}}}},
                    }],
                }],
            }])
        if request.url.path.endswith("/properties/content"):
            return httpx.Response(200, json={
                "hotel": {
                    "name": "Hotel",
                    "address": {
                        "line_1": "Hidden street",
                        "city": "Jaipur",
                        "country_code": "IN",
                        "obfuscation_required": True,
                    },
                    "location": {
                        "obfuscation_required": True,
                        "coordinates": {"latitude": 1, "longitude": 1},
                        "obfuscated_coordinates": {"latitude": 26, "longitude": 75},
                    },
                }
            })
        raise AssertionError(request.url)

    check_in, check_out = _future_stay()
    result = asyncio.run(_client(handler).search(
        destination="Jaipur",
        check_in=check_in,
        check_out=(date.fromisoformat(check_in) + timedelta(days=1)).isoformat(),
        adults=2,
        rooms=1,
        child_ages=[],
        currency="INR",
        session_id="session",
    ))
    offer = result["offers"][0]
    assert offer["address"] == {"city": "Jaipur", "country_code": "IN"}
    assert (offer["latitude"], offer["longitude"]) == (26, 75)


def test_stay_dates_are_validated():
    tomorrow = date.today() + timedelta(days=1)
    day_after = tomorrow + timedelta(days=1)
    with pytest.raises(ValueError):
        validate_stay("not-a-date", day_after.isoformat())
    with pytest.raises(ValueError):
        validate_stay(day_after.isoformat(), tomorrow.isoformat())
    with pytest.raises(ValueError):
        validate_stay(tomorrow.isoformat(), (tomorrow + timedelta(days=29)).isoformat())


def test_rapid_credentials_and_rate_limit_errors_are_explicit():
    with pytest.raises(HotelProviderNotConfigured):
        ExpediaRapidClient(api_key="", shared_secret="")._headers()

    def rate_limited(_request):
        return httpx.Response(429)

    client = _client(rate_limited)
    with pytest.raises(HotelProviderRateLimited):
        asyncio.run(client._get_json("regions"))
    asyncio.run(client.aclose())
