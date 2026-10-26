import csv

from app.agents.cost_estimator import (
    DEMO_ATTRACTIONS_PATH,
    DEMO_HOTELS_PATH,
    calculate_trip_costs,
    estimate_transport,
    load_demo_attractions,
    load_demo_hotels,
)


def _hotel(**overrides):
    return {
        "id": "hotel-1",
        "name": "Sample hotel",
        "destination": "Jaipur",
        "price": 1200,
        "price_per_night": 1200,
        "max_occupancy": 2,
        "data_status": "VERIFIED",
        "source_type": "verified",
        **overrides,
    }


def _route(**overrides):
    return {
        "origin": "Jaipur reference",
        "destination": "Attraction",
        "origin_id": "jaipur",
        "destination_id": 1,
        "distance_km": 5,
        "time_min": 10,
        "cost": 60,
        "status": "calculated",
        "mode": "car_taxi_estimate",
        "data_status": "ESTIMATE",
        "source_type": "estimate",
        **overrides,
    }


def _itinerary(attractions, *, hotel=None, route=None, return_route=None):
    return [{
        "day": 1,
        "hotel": hotel,
        "legs": [
            {"attraction": attraction, "transport": route or _route()}
            for attraction in attractions
        ],
        "return_transport": return_route,
    }]


def _calculate(itinerary, **overrides):
    return calculate_trip_costs(
        itinerary,
        duration=overrides.pop("duration", 2),
        travelers=overrides.pop("travelers", 1),
        budget_limit=overrides.pop("budget_limit", 10000),
        currency="INR",
        **overrides,
    )


def test_attraction_entry_cost_is_per_traveler_and_group_charge_is_not_multiplied():
    itinerary = _itinerary([
        {"id": 1, "name": "Museum", "cost": 100},
        {"id": 2, "name": "Group pass", "cost": 250, "cost_basis": "group"},
    ])
    result = _calculate(itinerary, travelers=3)
    assert result["attraction_total"] == 550


def test_verified_free_attraction_is_not_unknown():
    result = _calculate(_itinerary([{"id": 1, "name": "Park", "cost": 0}]))
    assert result["attraction_total"] == 0
    assert result["attraction_cost_complete"] is True


def test_unknown_attraction_fee_is_excluded_and_marks_total_incomplete():
    result = _calculate(_itinerary([{"id": 1, "name": "Unknown fee", "cost": None}]))
    assert result["attraction_total"] is None
    assert result["attraction_cost_complete"] is False
    assert result["excluded_attractions"][0]["id"] == 1
    assert result["is_estimate_complete"] is False


def test_transport_uses_configurable_straight_line_cost_estimate(monkeypatch):
    monkeypatch.setenv("WANDERWISE_TRANSPORT_COST_PER_KM", "15")
    route = estimate_transport(
        {"id": "a", "name": "A", "latitude": 26.9124, "longitude": 75.7873},
        {"id": "b", "name": "B", "latitude": 26.92, "longitude": 75.8},
    )
    assert route["status"] == "calculated"
    assert route["method"] == "haversine_straight_line_estimate"
    assert route["data_status"] == "ESTIMATE"
    assert route["distance_km"] > 0
    assert route["cost"] == round(route["distance_km"] * 15, 2)
    assert route["time_min"] > 0


def test_unavailable_route_has_no_cost_and_is_not_free():
    route = estimate_transport(
        {"id": "a", "name": "A", "latitude": None, "longitude": None},
        {"id": "b", "name": "B", "latitude": 26.92, "longitude": 75.8},
    )
    assert route["status"] == "unavailable"
    assert route["cost"] is None
    assert "excluded" in route["reason"]


def test_duplicate_attractions_and_same_day_transport_legs_are_counted_once():
    item = {"id": 1, "name": "Museum", "cost": 100}
    itinerary = _itinerary(
        [item, item],
        route=_route(source_type="synthetic", data_status="DEMO_SYNTHETIC"),
    )
    result = _calculate(itinerary, travelers=2)
    assert result["attraction_total"] == 200
    assert result["transportation_total"] == 60
    assert result["demonstration_cost_total"] == 60
    assert len(result["excluded_attractions"]) == 1
    assert result["transport_leg_count"] == 1


def test_accommodation_multiplies_nights_and_rooms_for_occupancy():
    result = _calculate(
        _itinerary([], hotel=_hotel()),
        duration=4,
        travelers=3,
    )
    assert result["accommodation"]["nights"] == 3
    assert result["accommodation"]["rooms_required"] == 2
    assert result["accommodation_total"] == 7200


def test_hotel_occupancy_is_not_assumed():
    result = _calculate(
        _itinerary([], hotel=_hotel(max_occupancy=None)),
        duration=3,
        travelers=2,
    )
    assert result["accommodation_total"] is None
    assert result["accommodation_cost_complete"] is False
    assert "occupancy is unknown" in result["accommodation"]["reason"]


def test_missing_accommodation_price_does_not_become_zero():
    result = _calculate(
        _itinerary([], hotel=_hotel(price=None, price_per_night=None)),
        duration=3,
    )
    assert result["accommodation_total"] is None
    assert result["accommodation_cost_complete"] is False
    assert "price is unavailable" in result["accommodation"]["reason"]


def test_demo_hotel_matching_is_destination_scoped_and_synthetic(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_DATA", "true")
    hotels = load_demo_hotels("Jaipur", "Rajasthan", 26.9124, 75.7873)
    assert len(hotels) == 1
    assert hotels[0]["data_status"] == "DEMO_SYNTHETIC"
    assert hotels[0]["source_type"] == "synthetic"
    assert "not a real property address" in hotels[0]["address"]
    assert load_demo_hotels("Unrelated City", "Other State", 26.9124, 75.7873) == []


def test_kerala_alias_resolves_to_backwaters_demo_hotel(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_DATA", "true")
    hotels = load_demo_hotels("Kerala Backwaters", "Kerala", 9.4981, 76.3388)
    assert len(hotels) == 1
    assert hotels[0]["destination"] == "Kerala Backwaters (Alappuzha & Kumarakom)"


def test_demo_hotels_are_enabled_by_default(monkeypatch):
    monkeypatch.delenv("WANDERWISE_DEMO_DATA", raising=False)
    monkeypatch.delenv("WANDERWISE_DEMO_HOTELS", raising=False)
    hotels = load_demo_hotels("Jaipur", "Rajasthan", 26.9124, 75.7873)
    assert len(hotels) == 1
    assert hotels[0]["source_type"] == "synthetic"


def test_demo_hotels_can_be_disabled(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_HOTELS", "false")
    assert load_demo_hotels("Jaipur", "Rajasthan", 26.9124, 75.7873) == []


def test_demo_attractions_are_labeled_and_have_consistent_fees(monkeypatch):
    monkeypatch.delenv("WANDERWISE_DEMO_DATA", raising=False)
    monkeypatch.delenv("WANDERWISE_DEMO_ATTRACTIONS", raising=False)
    attractions = load_demo_attractions("Jaipur", "Rajasthan", 26.9124, 75.7873)

    assert len(attractions) == 3
    assert all(item["source_type"] == "synthetic" for item in attractions)
    assert all(item["data_status"] == "DEMO_SYNTHETIC" for item in attractions)
    assert all(item["duration"] > 0 for item in attractions)
    assert all(item["fee_status"] == ("DEMO_FREE" if item["cost"] == 0 else "DEMO_PAID") for item in attractions)


def test_demo_attractions_can_be_disabled(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_ATTRACTIONS", "false")
    assert load_demo_attractions("Jaipur", "Rajasthan", 26.9124, 75.7873) == []


def test_demo_catalog_has_twenty_destinations_with_three_attractions_each():
    with DEMO_ATTRACTIONS_PATH.open(newline="", encoding="utf-8-sig") as data_file:
        rows = list(csv.DictReader(data_file))

    destination_names = {row["destination_name"] for row in rows}
    assert len(destination_names) == 20
    assert all(
        sum(row["destination_name"] == name for row in rows) == 3
        for name in destination_names
    )


def test_demo_hotel_names_are_destination_specific_and_marked_fictional():
    with DEMO_HOTELS_PATH.open(newline="", encoding="utf-8-sig") as data_file:
        rows = list(csv.DictReader(data_file))

    names = [row["sample_property_name"] for row in rows]
    assert len(names) == 20
    assert len(set(names)) == 20
    assert all(name and "(fictional demo stay)" not in name for name in names)


def test_all_known_components_sum_once_and_remaining_is_arithmetic():
    itinerary = _itinerary(
        [{"id": 1, "name": "Museum", "cost": 100}],
        hotel=_hotel(),
        route=_route(cost=70),
        return_route=_route(
            origin="Attraction",
            destination="Jaipur reference",
            origin_id=1,
            destination_id="jaipur",
            cost=80,
        ),
    )
    result = _calculate(itinerary, duration=2, travelers=2, budget_limit=20000)
    assert result["attraction_total"] == 200
    assert result["transportation_total"] == 150
    assert result["accommodation_total"] == 1200
    assert result["known_cost_total"] == 1550
    assert result["remaining_budget_after_known_costs"] == 18450


def test_incomplete_total_still_reports_arithmetic_remainder_but_not_spendable():
    result = _calculate(
        _itinerary([{"id": 1, "name": "Unknown", "cost": None}], route={
            **_route(), "status": "unavailable", "cost": None,
        }),
        budget_limit=5000,
    )
    assert result["remaining_budget_after_known_costs"] == 5000
    assert result["remaining_budget_is_spendable"] is False
    assert result["is_estimate_complete"] is False


def test_synthetic_accommodation_is_separately_classified(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_DATA", "true")
    hotel = _hotel(data_status="DEMO_SYNTHETIC", source_type="synthetic")
    result = _calculate(_itinerary([], hotel=hotel), duration=3)
    assert result["accommodation"]["data_status"] == "DEMO_SYNTHETIC"
    assert result["demonstration_cost_total"] == result["accommodation_total"]
    assert result["illustrative_total"] == result["known_cost_total"]
    assert result["remaining_budget_is_spendable"] is False
    assert result["remaining_budget_status"] == "illustrative_demo_only"
