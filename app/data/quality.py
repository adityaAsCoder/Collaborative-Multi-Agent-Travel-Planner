"""Validation helpers for location and source-backed catalog values."""

from __future__ import annotations

import math
import re
from typing import Any


INDIA_BOUNDS = (6.0, 38.0, 68.0, 98.0)
MAX_LOCAL_DISTANCE_KM = 300.0


def finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def has_verified_source(source: Any) -> bool:
    if not isinstance(source, str) or not source.strip():
        return False
    normalized = source.strip().casefold()
    return not any(
        marker in normalized
        for marker in (
            "estimate",
            "unverified",
            "unknown",
            "undated",
            "unavailable",
            "missing",
        )
    )


def verified_measure(
    value: Any,
    source: Any,
    *,
    minimum: float,
    maximum: float | None = None,
    validation_status: Any = None,
) -> float | None:
    number = finite_number(value)
    if number is None or not has_verified_source(source) or number < minimum:
        return None
    if validation_status is not None:
        status = str(validation_status).strip().casefold()
        if status not in {"verified", "validated", "source_verified"}:
            return None
    if maximum is not None and number > maximum:
        return None
    return number


def valid_india_coordinates(latitude: Any, longitude: Any) -> bool:
    lat = finite_number(latitude)
    lon = finite_number(longitude)
    south, north, west, east = INDIA_BOUNDS
    return lat is not None and lon is not None and south <= lat <= north and west <= lon <= east


def haversine_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    radius_km = 6371.0
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def verified_coordinates(
    latitude: Any,
    longitude: Any,
    source: Any,
    status: Any,
    destination_latitude: Any = None,
    destination_longitude: Any = None,
) -> tuple[float, float] | None:
    lat = finite_number(latitude)
    lon = finite_number(longitude)
    if (
        lat is None
        or lon is None
        or not valid_india_coordinates(lat, lon)
        or not has_verified_source(source)
        or str(status or "").strip().casefold() not in {"resolved", "verified", "validated"}
    ):
        return None

    dest_lat = finite_number(destination_latitude)
    dest_lon = finite_number(destination_longitude)
    if dest_lat is not None and dest_lon is not None:
        if not valid_india_coordinates(dest_lat, dest_lon):
            return None
        if haversine_km(lat, lon, dest_lat, dest_lon) > MAX_LOCAL_DISTANCE_KM:
            return None
    return lat, lon


def _normalized_location(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def destination_location_terms(destination_name: str, state: str | None = None) -> list[str]:
    """Extract exact city/region labels; never use substring fragments."""
    name = destination_name.strip()
    aliases = re.findall(r"\(([^)]*)\)", name)
    primary = re.sub(r"\([^)]*\)", "", name).strip()
    terms = [primary]
    for alias_group in aliases:
        terms.extend(re.split(r"\s*(?:&|,|\band\b)\s*", alias_group, flags=re.IGNORECASE))
    if state and _normalized_location(name) == _normalized_location(state):
        terms.append(state)
    return list(dict.fromkeys(term for term in (_normalized_location(t) for t in terms) if term))


def address_matches_destination(address: Any, destination_name: str, state: str | None = None) -> bool:
    if not isinstance(address, str) or not address.strip():
        return False
    segments = [_normalized_location(part) for part in address.split(",") if part.strip()]
    recent_segments = segments[-2:]
    terms = destination_location_terms(destination_name, state)
    return any(
        segment == term or segment.endswith(f" {term}")
        for segment in recent_segments
        for term in terms
    )
