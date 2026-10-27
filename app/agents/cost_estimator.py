"""Shared trip-cost calculations and clearly labeled demonstration data."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import re
from typing import Any

from app.data.quality import (
    destination_location_terms,
    finite_number,
    haversine_km,
    valid_india_coordinates,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_HOTELS_PATH = PROJECT_ROOT / "datasets" / "demo" / "demo_hotels.csv"
DEMO_ATTRACTIONS_PATH = PROJECT_ROOT / "datasets" / "demo" / "demo_attractions.csv"
TRANSPORT_CONFIG_PATH = PROJECT_ROOT / "datasets" / "demo" / "demo_transport.json"


def demo_data_enabled() -> bool:
    return os.environ.get("WANDERWISE_DEMO_DATA", "").strip().casefold() in {
        "1", "true", "yes", "on",
    }


def demo_attractions_enabled() -> bool:
    setting = os.environ.get(
        "WANDERWISE_DEMO_ATTRACTIONS",
        os.environ.get("WANDERWISE_DEMO_DATA", "true"),
    )
    return setting.strip().casefold() in {
        "1", "true", "yes", "on",
    }


def demo_hotels_enabled() -> bool:
    setting = os.environ.get(
        "WANDERWISE_DEMO_HOTELS",
        os.environ.get("WANDERWISE_DEMO_DATA", "true"),
    )
    return setting.strip().casefold() in {
        "1", "true", "yes", "on",
    }


def _transport_settings() -> dict[str, float]:
    with TRANSPORT_CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

    def configured_value(environment_key: str, config_key: str) -> float | None:
        raw_environment_value = os.environ.get(environment_key)
        if raw_environment_value is not None:
            value = finite_number(raw_environment_value)
            if value is None or value <= 0:
                raise ValueError(f"{environment_key} must be a positive number.")
            return value
        return finite_number(config.get(config_key))

    rate = configured_value(
        "WANDERWISE_TRANSPORT_COST_PER_KM", "illustrative_cost_per_km_inr"
    )
    speed = configured_value(
        "WANDERWISE_ESTIMATED_SPEED_KMH", "estimated_speed_kmh"
    )
    if rate is None or rate <= 0 or speed is None or speed <= 0:
        raise ValueError("Transportation cost and speed configuration must be positive numbers.")
    return {"cost_per_km": rate, "speed_kmh": speed}


def load_demo_hotels(
    destination_name: str,
    destination_state: str | None,
    reference_latitude: float | None,
    reference_longitude: float | None,
) -> list[dict[str, Any]]:
    """Load synthetic hotels only for a destination with a sourced reference point."""
    if not demo_hotels_enabled():
        return []
    if (
        reference_latitude is None
        or reference_longitude is None
        or not valid_india_coordinates(reference_latitude, reference_longitude)
    ):
        return []

    destination_terms = set(destination_location_terms(destination_name, destination_state))
    if destination_state:
        destination_terms.add(" ".join(destination_state.casefold().split()))

    results = []
    with DEMO_HOTELS_PATH.open(newline="", encoding="utf-8-sig") as data_file:
        for row in csv.DictReader(data_file):
            row_terms = set(destination_location_terms(row.get("destination_name", "")))
            if not destination_terms.intersection(row_terms):
                continue
            if (
                row.get("data_status") != "DEMO_SYNTHETIC"
                or row.get("source_type") != "synthetic"
                or not row.get("location_reference")
            ):
                raise ValueError(
                    f"Synthetic hotel {row.get('demo_hotel_id')} is missing its demo provenance."
                )
            nightly_rate = finite_number(row.get("illustrative_price_per_night"))
            occupancy = finite_number(row.get("max_occupancy"))
            if nightly_rate is None or nightly_rate <= 0 or occupancy is None or occupancy < 1:
                raise ValueError(
                    f"Invalid synthetic hotel pricing or occupancy for {row.get('demo_hotel_id')}."
                )
            results.append({
                "id": row["demo_hotel_id"],
                "name": row["sample_property_name"],
                "destination": row["destination_name"],
                "address": (
                    f"Demonstration location near the {destination_name} reference point; "
                    "not a real property address."
                ),
                "latitude": reference_latitude,
                "longitude": reference_longitude,
                "price": nightly_rate,
                "price_per_night": nightly_rate,
                "rating": None,
                "max_occupancy": int(occupancy),
                "currency": "INR",
                "data_status": "DEMO_SYNTHETIC",
                "source_type": "synthetic",
                "location_reference": row["location_reference"],
                "description": row["description"],
            })
    return results


def load_demo_attractions(
    destination_name: str,
    destination_state: str | None,
    reference_latitude: float | None,
    reference_longitude: float | None,
) -> list[dict[str, Any]]:
    """Load explicitly synthetic attraction and fee details for demo destinations."""
    if not demo_attractions_enabled():
        return []
    if (
        reference_latitude is None
        or reference_longitude is None
        or not valid_india_coordinates(reference_latitude, reference_longitude)
    ):
        return []

    destination_terms = set(destination_location_terms(destination_name, destination_state))
    results = []
    coordinate_offsets = ((0.003, 0.004), (0.006, -0.005), (-0.004, 0.007))
    with DEMO_ATTRACTIONS_PATH.open(newline="", encoding="utf-8-sig") as data_file:
        for row in csv.DictReader(data_file):
            row_terms = set(destination_location_terms(row.get("destination_name", "")))
            if not destination_terms.intersection(row_terms):
                continue

            fee = finite_number(row.get("illustrative_entry_fee_inr"))
            duration = finite_number(row.get("visit_duration_min"))
            fee_status = row.get("fee_status")
            if fee_status in {"PAID", "FREE"}:
                fee_status = "DEMO_FREE" if fee == 0 else "DEMO_PAID"
            if fee is None or fee < 0 or duration is None or duration < 1:
                raise ValueError(
                    f"Invalid demonstration fee or visit duration for {row.get('attraction_name')}."
                )
            if fee_status != ("DEMO_FREE" if fee == 0 else "DEMO_PAID"):
                raise ValueError(
                    f"Demonstration fee status does not match the fee for {row.get('attraction_name')}."
                )

            offset_latitude, offset_longitude = coordinate_offsets[len(results) % len(coordinate_offsets)]
            latitude = round(reference_latitude + offset_latitude, 6)
            longitude = round(reference_longitude + offset_longitude, 6)
            if not valid_india_coordinates(latitude, longitude):
                raise ValueError(
                    f"Demonstration coordinates fall outside India for {row.get('attraction_name')}."
                )
            destination_slug = re.sub(
                r"[^a-z0-9]+", "-", row["destination_name"].casefold()
            ).strip("-")
            interest_tags = row.get("interest_tags", "").strip()
            results.append({
                "id": f"demo-attraction-{destination_slug}-{len(results) + 1}",
                "name": row["attraction_name"],
                "category": row["category"],
                "subcategory": row["subcategory"],
                "rating": None,
                "cost": fee,
                "cost_basis": "per_person",
                "cost_currency": "INR",
                "cost_data_status": "DEMO_SYNTHETIC",
                "cost_validation_status": "demo",
                "fee_status": fee_status,
                "duration": int(duration),
                "duration_validation_status": "demo",
                "description": f"Illustrative demonstration attraction tagged for {interest_tags} interests.",
                "latitude": latitude,
                "longitude": longitude,
                "coordinate_status": "demo",
                "coordinate_reason": (
                    "Illustrative offset from the destination reference point; "
                    "not a verified attraction location."
                ),
                "data_status": "DEMO_SYNTHETIC",
                "source_type": "synthetic",
            })
    return results


def estimate_transport(
    origin: dict[str, Any] | None,
    destination: dict[str, Any] | None,
    *,
    mode: str = "car_taxi_estimate",
) -> dict[str, Any]:
    """Estimate straight-line distance, duration, and cost without claiming road routing."""
    origin_name = (origin or {}).get("name")
    destination_name = (destination or {}).get("name")
    origin_id = (origin or {}).get("id")
    destination_id = (destination or {}).get("id")

    def unavailable(reason: str) -> dict[str, Any]:
        return {
            "origin": origin_name,
            "destination": destination_name,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "distance_km": None,
            "time_min": None,
            "cost": None,
            "status": "unavailable",
            "method": None,
            "mode": mode,
            "data_status": "unavailable",
            "source_type": None,
            "reason": reason,
        }

    if not origin or not destination:
        return unavailable("The origin or destination location is unavailable; this leg is excluded.")

    olat = finite_number(origin.get("latitude"))
    olon = finite_number(origin.get("longitude"))
    dlat = finite_number(destination.get("latitude"))
    dlon = finite_number(destination.get("longitude"))
    if (
        olat is None or olon is None or dlat is None or dlon is None
        or not valid_india_coordinates(olat, olon)
        or not valid_india_coordinates(dlat, dlon)
    ):
        return unavailable("Validated coordinates are unavailable; this leg is excluded.")

    settings = _transport_settings()
    distance_km = haversine_km(olat, olon, dlat, dlon)
    travel_minutes = distance_km / settings["speed_kmh"] * 60
    is_demo = (
        demo_data_enabled()
        or (origin or {}).get("source_type") == "synthetic"
        or (destination or {}).get("source_type") == "synthetic"
    )
    return {
        "origin": origin_name or "Itinerary location",
        "destination": destination_name or "Itinerary location",
        "origin_id": origin_id,
        "destination_id": destination_id,
        "distance_km": round(distance_km, 2),
        "time_min": round(travel_minutes),
        "cost": round(round(distance_km, 2) * settings["cost_per_km"], 2),
        "cost_per_km": settings["cost_per_km"],
        "status": "calculated",
        "method": "haversine_straight_line_estimate",
        "mode": mode,
        "data_status": "DEMO_SYNTHETIC" if is_demo else "ESTIMATE",
        "source_type": "synthetic" if is_demo else "estimate",
        "reason": (
            "Straight-line distance, duration, and configured per-kilometre cost estimate; "
            "not a road route, live fare, or verified market price."
        ),
    }


def calculate_trip_costs(
    itinerary: list[dict[str, Any]],
    *,
    duration: int,
    travelers: int,
    budget_limit: float | None,
    currency: str,
    accommodation_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate every cost component once, retaining partial totals and provenance."""
    nights = max(0, duration - 1)
    selected_hotel = next((day.get("hotel") for day in itinerary if day.get("hotel")), None)
    unknown_components: list[str] = []
    excluded_attractions: list[dict[str, Any]] = []
    excluded_transport_legs: list[dict[str, Any]] = []
    seen_attractions: set[Any] = set()
    attraction_total = 0.0
    attraction_count = 0
    demonstration_attraction_count = 0
    demonstration_attraction_total = 0.0
    unknown_attraction_count = 0
    accommodation = {
        "hotel_id": None,
        "hotel_name": None,
        "destination": None,
        "address": None,
        "latitude": None,
        "longitude": None,
        "rating": None,
        "currency": currency,
        "price_per_night": None,
        "nights": nights,
        "rooms_required": None,
        "total_accommodation_cost": None,
        "data_status": "unavailable",
        "source_type": None,
        "reason": (accommodation_status or {}).get(
            "reason", "No suitable accommodation was selected; accommodation is not free."
        ),
    }
    accommodation_complete = False
    accommodation_cost = None

    if selected_hotel:
        price = finite_number(selected_hotel.get("price_per_night", selected_hotel.get("price")))
        occupancy = finite_number(selected_hotel.get("max_occupancy"))
        accommodation.update({
            "hotel_id": selected_hotel.get("id"),
            "hotel_name": selected_hotel.get("name"),
            "destination": selected_hotel.get("destination"),
            "address": selected_hotel.get("address"),
            "latitude": selected_hotel.get("latitude"),
            "longitude": selected_hotel.get("longitude"),
            "rating": selected_hotel.get("rating"),
            "currency": selected_hotel.get("currency", currency),
            "price_per_night": price,
            "data_status": selected_hotel.get("data_status", "VERIFIED"),
            "source_type": selected_hotel.get("source_type", "verified"),
        })
        if price is None or price <= 0:
            accommodation["reason"] = "A valid nightly accommodation price is unavailable."
        elif occupancy is None or occupancy < 1:
            accommodation["reason"] = (
                "Nightly price is available, but room occupancy is unknown; "
                "the room count and trip accommodation total are not estimated."
            )
        else:
            rooms = math.ceil(travelers / occupancy)
            accommodation_cost = round(price * nights * rooms, 2)
            accommodation_complete = True
            accommodation.update({
                "rooms_required": rooms,
                "total_accommodation_cost": accommodation_cost,
                "reason": None,
            })
    elif nights == 0:
        accommodation["reason"] = (
            "No overnight stay is required for this one-day itinerary; no hotel was selected."
        )
        accommodation["data_status"] = "NOT_REQUIRED"
        accommodation_complete = True
        accommodation_cost = 0.0

    if not accommodation_complete:
        unknown_components.append(accommodation["reason"] or "Accommodation cost is unavailable.")

    transportation_total = 0.0
    estimated_transport_total = 0.0
    demonstration_transport_total = 0.0
    transport_count = 0
    unknown_transport_count = 0
    seen_routes: set[tuple[Any, ...]] = set()
    for day in itinerary:
        day_number = day.get("day")
        for leg in day.get("legs", []):
            attraction = leg.get("attraction") or {}
            attraction_id = attraction.get("id")
            attraction_key = ("id", attraction_id) if attraction_id is not None else (
                "name", str(attraction.get("name", "")).casefold(),
            )
            if attraction_key in seen_attractions:
                excluded_attractions.append({
                    "id": attraction_id,
                    "name": attraction.get("name"),
                    "reason": "Duplicate attraction; entry fee counted once.",
                })
            else:
                seen_attractions.add(attraction_key)
                fee = finite_number(attraction.get("cost"))
                if fee is None or fee < 0:
                    unknown_attraction_count += 1
                    excluded_attractions.append({
                        "id": attraction_id,
                        "name": attraction.get("name"),
                        "reason": "Entry fee is unknown and excluded from the known total.",
                    })
                else:
                    visitors = 1 if attraction.get("cost_basis") == "group" else travelers
                    attraction_cost = fee * visitors
                    attraction_total += attraction_cost
                    if attraction.get("source_type") == "synthetic":
                        demonstration_attraction_total += attraction_cost
                        demonstration_attraction_count += 1
                    attraction_count += 1

            route = leg.get("transport") or {}
            route_key = (
                day_number,
                route.get("origin_id") or route.get("origin"),
                route.get("destination_id") or route.get("destination") or attraction_id,
                route.get("mode"),
            )
            if route_key in seen_routes:
                continue
            seen_routes.add(route_key)
            route_cost = finite_number(route.get("cost"))
            if route.get("status") != "calculated" or route_cost is None or route_cost < 0:
                unknown_transport_count += 1
                excluded_transport_legs.append({
                    "origin": route.get("origin"),
                    "destination": route.get("destination") or attraction.get("name"),
                    "reason": route.get("reason") or "Route could not be calculated.",
                })
            else:
                transportation_total += route_cost
                if route.get("source_type") == "synthetic":
                    demonstration_transport_total += route_cost
                else:
                    estimated_transport_total += route_cost
                transport_count += 1

        return_route = day.get("return_transport")
        if return_route:
            route_key = (
                day_number,
                return_route.get("origin_id") or return_route.get("origin"),
                return_route.get("destination_id") or return_route.get("destination"),
                return_route.get("mode"),
            )
            if route_key not in seen_routes:
                seen_routes.add(route_key)
                route_cost = finite_number(return_route.get("cost"))
                if return_route.get("status") != "calculated" or route_cost is None or route_cost < 0:
                    unknown_transport_count += 1
                    excluded_transport_legs.append({
                        "origin": return_route.get("origin"),
                        "destination": return_route.get("destination"),
                        "reason": return_route.get("reason") or "Return route could not be calculated.",
                    })
                else:
                    transportation_total += route_cost
                    if return_route.get("source_type") == "synthetic":
                        demonstration_transport_total += route_cost
                    else:
                        estimated_transport_total += route_cost
                    transport_count += 1

    attraction_complete = unknown_attraction_count == 0
    transportation_complete = unknown_transport_count == 0
    if unknown_attraction_count:
        unknown_components.append(
            f"Entry fees are unavailable for {unknown_attraction_count} attraction(s)."
        )
    if unknown_transport_count:
        unknown_components.append(
            f"Transportation is unavailable for {unknown_transport_count} itinerary leg(s)."
        )

    component_amounts = {
        "attraction": attraction_total,
        "transportation": transportation_total,
        "accommodation": accommodation_cost,
    }
    known_cost_total = round(sum(value for value in component_amounts.values() if value is not None), 2)
    has_known_costs = bool(attraction_count or transport_count or accommodation_cost is not None)
    attraction_component = (
        round(attraction_total, 2)
        if attraction_count or unknown_attraction_count == 0 else None
    )
    transportation_component = (
        round(transportation_total, 2)
        if transport_count or unknown_transport_count == 0 else None
    )
    is_complete = (
        accommodation_complete and attraction_complete and transportation_complete
    )
    verified_total = 0.0
    estimated_total = estimated_transport_total
    demonstration_total = demonstration_attraction_total
    if attraction_count:
        verified_total += attraction_total - demonstration_attraction_total
    elif not itinerary:
        verified_total += 0.0

    if accommodation_cost is not None:
        if accommodation["source_type"] == "synthetic":
            demonstration_total += accommodation_cost
        elif accommodation["data_status"] != "NOT_REQUIRED":
            verified_total += accommodation_cost

    demonstration_total += demonstration_transport_total

    has_demo_values = (
        demonstration_attraction_count > 0
        or demonstration_transport_total > 0
        or accommodation.get("source_type") == "synthetic"
    )
    remaining = (
        round(budget_limit - known_cost_total, 2)
        if budget_limit is not None else None
    )
    return {
        "attraction_total": attraction_component,
        "transportation_total": transportation_component,
        "accommodation_total": accommodation_cost,
        "other_expenses_total": 0.0,
        "known_cost_total": known_cost_total,
        "verified_cost_total": round(verified_total, 2),
        "estimated_cost_total": round(estimated_total, 2),
        "demonstration_cost_total": round(demonstration_total, 2),
        "illustrative_total": known_cost_total if has_demo_values else None,
        "budget_limit": budget_limit,
        "remaining_budget_after_known_costs": remaining,
        "remaining_budget_is_spendable": is_complete and not has_demo_values,
        "is_estimate_complete": is_complete,
        "data_status": (
            "DEMO_SYNTHETIC" if has_demo_values
            else "INCOMPLETE" if not is_complete
            else "ESTIMATE"
        ),
        "attraction_cost_complete": attraction_complete,
        "transport_cost_complete": transportation_complete,
        "accommodation_cost_complete": accommodation_complete,
        "attraction_count": attraction_count,
        "transport_leg_count": transport_count,
        "unknown_components": unknown_components,
        "excluded_attractions": excluded_attractions,
        "excluded_transport_legs": excluded_transport_legs,
        "accommodation": accommodation,
        "accommodation_cost": accommodation_cost,
        "attraction_cost": attraction_component,
        "transport_cost": transportation_component,
        "daily_cost": (
            round(known_cost_total / max(1, duration), 2) if has_known_costs else None
        ),
        "total_estimated_cost": known_cost_total if has_known_costs else None,
        "total_is_complete": is_complete,
        "remaining_budget_status": (
            "illustrative_demo_only" if has_demo_values
            else "complete" if is_complete
            else "unavailable_incomplete_costs"
        ),
        "remaining_budget": remaining,
        "currency": currency,
    }
