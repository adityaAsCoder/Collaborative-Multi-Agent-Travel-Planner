from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import implementations
from app.agents.implementations import (
    AccommodationAgent,
    BudgetAgent,
    OptimizationAgent,
    PlannerAgent,
    PreferenceAgent,
    TransportAgent,
)
from app.data.models import Attraction, Base, Destination, Hotel
from app.data.preferences import matched_interests
from app.data.quality import (
    address_matches_destination,
    verified_coordinates,
    verified_measure,
)
from app.schemas.planning import PlanningRequest


def _request(**overrides):
    values = {
        "destination": "Jaipur",
        "duration": 6,
        "travelers": 2,
        "budget": 100000,
        "currency": "INR",
        "interests": ["History", "Forts"],
        "accommodation_preference": "any",
    }
    values.update(overrides)
    return PlanningRequest(**values)


def test_unknown_fee_is_not_zero_but_sourced_zero_is_free():
    assert verified_measure(None, "official entry page", minimum=0) is None
    assert verified_measure(0, "estimated", minimum=0) is None
    assert verified_measure(0, "official entry page", minimum=0) == 0


def test_missing_duration_remains_unavailable():
    assert verified_measure(None, "official visitor guide", minimum=1) is None
    assert verified_measure(0, "official visitor guide", minimum=1) is None


def test_unverified_invalid_and_swapped_coordinates_are_rejected():
    assert verified_coordinates(None, 76.3, "OSM", "resolved") is None
    assert verified_coordinates(91, 76.3, "OSM", "resolved") is None
    assert verified_coordinates(76.3, 9.5, "OSM", "resolved") is None
    assert verified_coordinates(9.5, 76.3, "destination-center estimate", "estimated") is None


def test_transport_failure_does_not_return_fake_zero_values():
    route = TransportAgent().run({
        "origin": None,
        "destination": {"latitude": 9.5, "longitude": 76.3},
    })
    assert route["status"] == "unavailable"
    assert route["distance_km"] is None
    assert route["time_min"] is None
    assert route["cost"] is None
    assert route["reason"]


def test_verified_transport_is_explicitly_straight_line_estimate():
    route = TransportAgent().run({
        "origin": {"latitude": 26.9, "longitude": 75.8},
        "destination": {"latitude": 26.9, "longitude": 75.8},
    })
    assert route["status"] == "calculated"
    assert route["distance_km"] == 0
    assert route["method"] == "haversine_straight_line_estimate"


def test_budget_marks_missing_costs_and_accommodation_incomplete():
    result = BudgetAgent().run({
        "duration": 3,
        "total_budget": 20000,
        "itinerary": [{
            "hotel": None,
            "legs": [{
                "attraction": {"cost": None},
                "transport": {"status": "unavailable", "cost": None},
            }],
        }],
    })
    assert result["accommodation_cost"] is None
    assert result["attraction_cost"] is None
    assert result["transport_cost"] is None
    assert result["total_estimated_cost"] is None
    assert result["remaining_budget"] is None
    assert result["total_is_complete"] is False
    assert result["remaining_budget_status"] == "unavailable_incomplete_costs"
    assert result["unknown_components"]


def test_known_zero_components_are_counted_as_known():
    result = BudgetAgent().run({
        "duration": 1,
        "total_budget": 5000,
        "itinerary": [{
            "hotel": None,
            "legs": [{
                "attraction": {"cost": 0},
                "transport": {"status": "calculated", "cost": 0},
            }],
        }],
    })
    assert result["attraction_cost"] == 0
    assert result["transport_cost"] == 0
    assert result["total_estimated_cost"] == 0
    assert result["total_is_complete"] is True


def test_normalized_interest_synonyms_match_attraction_text():
    attraction = {"name": "Amer Fort", "category": None, "subcategory": None}
    assert matched_interests(attraction, ["forts", "History"]) == ["forts", "History"]
    assert PreferenceAgent().run({
        "interests": ["beaches"],
        "candidate_attractions": [{"id": 1, "name": "Calangute Beach"}],
    }) == {1: 10.0}


def test_address_matching_uses_location_boundaries_not_substrings():
    assert not address_matches_destination("Agrahara Dasarahalli, Bangalore", "Agra")
    assert address_matches_destination("Alappuzha, Kerala", "Kerala Backwaters (Alappuzha & Kumarakom)")


def test_wrong_destination_hotel_and_unpriced_hotel_are_not_selected(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        jaipur = Destination(destination_name="Jaipur", state="Rajasthan", latitude=26.9, longitude=75.8)
        agra = Destination(destination_name="Agra", state="Uttar Pradesh", latitude=27.2, longitude=78.0)
        db.add_all([jaipur, agra])
        db.flush()
        db.add_all([
            Hotel(
                name="Wrong city hotel",
                normalized_name="wrong city hotel",
                destination_id=jaipur.destination_id,
                address="Agra, Uttar Pradesh",
                latitude=26.9,
                longitude=75.8,
                provenance_source="OpenStreetMap",
                data_quality_status="resolved",
                price_per_night=2000,
                source="hotel catalog",
            ),
            Hotel(
                name="Unpriced Jaipur hotel",
                normalized_name="unpriced jaipur hotel",
                destination_id=jaipur.destination_id,
                address="Jaipur",
                latitude=26.9,
                longitude=75.8,
                provenance_source="OpenStreetMap",
                data_quality_status="resolved",
                price_per_night=None,
                source="hotel catalog",
            ),
        ])
        db.commit()
    monkeypatch.setattr(implementations, "SessionLocal", session_factory)

    agent = AccommodationAgent()
    assert agent.run({"destination": "Jaipur"}) == []
    assert agent.last_status["status"] == "unavailable"
    assert agent.last_status["matched_hotel_count"] == 1
    assert agent.last_status["missing_or_invalid_prices"] == 1
    engine.dispose()


def test_verified_hotel_price_is_selected_and_included_in_known_budget(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        destination = Destination(
            destination_name="Jaipur",
            state="Rajasthan",
            latitude=26.9124,
            longitude=75.7873,
        )
        db.add(destination)
        db.flush()
        db.add(Hotel(
            name="Sourced Jaipur Hotel",
            normalized_name="sourced jaipur hotel",
            destination_id=destination.destination_id,
            address="Jaipur, Rajasthan",
            latitude=26.9200,
            longitude=75.8100,
            provenance_source="OpenStreetMap",
            data_quality_status="verified",
            price_per_night=2500,
            price_source="verified property rate table",
            price_validation_status="verified",
            rating=4.5,
            rating_source="verified property source",
            rating_validation_status="verified",
        ))
        db.commit()
    monkeypatch.setattr(implementations, "SessionLocal", session_factory)

    agent = AccommodationAgent()
    selected = agent.run({"destination": "Jaipur"})
    assert len(selected) == 1
    assert selected[0]["price"] == 2500
    assert agent.last_status["status"] == "available"
    budget = BudgetAgent().run({
        "duration": 3,
        "total_budget": 20000,
        "itinerary": [
            {"hotel": selected[0], "legs": [{
                "attraction": {"cost": None},
                "transport": {"status": "unavailable", "cost": None},
            }]}
        ],
    })
    assert budget["accommodation_cost"] == 5000
    assert budget["total_estimated_cost"] == 5000
    assert budget["total_is_complete"] is False
    assert budget["remaining_budget"] is None
    engine.dispose()


def test_optimizer_distributes_multiple_unique_attractions_across_six_days():
    request = _request()
    attractions = [
        {
            "id": index,
            "name": f"Historic Fort {index}",
            "category": "Historical",
            "subcategory": "Fort",
            "cost": None,
            "duration": None,
            "latitude": None,
            "longitude": None,
        }
        for index in range(12)
    ]
    preferences = PreferenceAgent().run({
        "interests": request.interests,
        "candidate_attractions": attractions,
    })
    itinerary = OptimizationAgent().run({
        "request": request,
        "candidate_hotels": [],
        "candidate_attractions": attractions,
        "preference_scores": preferences,
    })
    assert len(itinerary) == 6
    assert [len(day["legs"]) for day in itinerary] == [2, 2, 2, 2, 2, 2]
    selected_ids = [
        leg["attraction"]["id"]
        for day in itinerary
        for leg in day["legs"]
    ]
    assert len(selected_ids) == len(set(selected_ids)) == 12


def test_optimizer_uses_fallback_candidates_after_interest_matches():
    request = _request()
    attractions = [
        {
            "id": index,
            "name": f"Place {index}",
            "category": "Fort" if index < 2 else "Beach",
            "cost": None,
            "duration": None,
        }
        for index in range(6)
    ]
    preferences = PreferenceAgent().run({
        "interests": request.interests,
        "candidate_attractions": attractions,
    })
    itinerary = OptimizationAgent().run({
        "request": request,
        "candidate_hotels": [],
        "candidate_attractions": attractions,
        "preference_scores": preferences,
    })
    scheduled = [
        leg
        for day in itinerary
        for leg in day["legs"]
    ]
    assert len(scheduled) == 6
    assert all(
        leg["attraction"]["id"] in preferences
        for day in itinerary[:2]
        for leg in day["legs"]
    )
    assert all(
        "Fallback recommendation" in leg["recommendation_reason"]
        for day in itinerary[2:]
        for leg in day["legs"]
    )


def test_fallback_is_explained_and_insufficient_candidates_are_not_invented():
    state = PlannerAgent().run(_request(
        destination="Kerala Backwaters (Alappuzha & Kumarakom)",
        interests=["Quantum Gardening"],
    ))
    assert len(state.optimized_itinerary) == 6
    assert sum(len(day["legs"]) for day in state.optimized_itinerary) == len(state.candidate_attractions)
    assert state.planning_note and "fallback" in state.planning_note.casefold()
    assert "Only 4 attraction record(s) were available" in state.planning_note
    assert "no attraction recommendation" in state.planning_note
    assert any(not day["legs"] for day in state.optimized_itinerary)
    assert all(
        "Fallback recommendation" in leg["recommendation_reason"]
        for day in state.optimized_itinerary
        for leg in day["legs"]
    )


def test_jaipur_request_remains_a_six_day_plan_without_duplicate_places():
    state = PlannerAgent().run(_request(destination="Jaipur"))
    assert len(state.optimized_itinerary) == 6
    attraction_ids = [
        leg["attraction"]["id"]
        for day in state.optimized_itinerary
        for leg in day["legs"]
    ]
    assert len(attraction_ids) == len(set(attraction_ids))
