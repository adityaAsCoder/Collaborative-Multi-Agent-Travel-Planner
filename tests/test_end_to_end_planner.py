"""End-to-end planner integration tests."""
import csv
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.agents.cost_estimator import DEMO_ATTRACTIONS_PATH
from app.schemas.planning import PlanningRequest, PlanningState
from app.agents.implementations import (
    ResearchAgent, PreferenceAgent, AccommodationAgent,
    TransportAgent, BudgetAgent, ConstraintAgent,
    OptimizationAgent, PlannerAgent
)


def _jaipur_request(**overrides):
    defaults = dict(
        destination="Jaipur",
        duration=3,
        travelers=2,
        budget=20000,
        currency="INR",
        interests=["Forts", "History", "Food"],
        accommodation_preference="standard",
    )
    defaults.update(overrides)
    return PlanningRequest(**defaults)


# ---------- 1. Valid planning request ----------
def test_valid_planning_request():
    req = _jaipur_request()
    agent = PlannerAgent()
    state = agent.run(req)
    assert state.optimized_itinerary is not None
    assert len(state.optimized_itinerary) == req.duration


# ---------- 2. Destination with available attractions ----------
def test_destination_has_attractions():
    req = _jaipur_request()
    ra = ResearchAgent()
    atts = ra.run({"destination": req.destination, "interests": req.interests})
    assert len(atts) > 0
    for a in atts:
        assert "id" in a
        assert "name" in a


# ---------- 3. No duplicate attractions ----------
def test_no_duplicate_attractions():
    req = _jaipur_request()
    state = PlannerAgent().run(req)
    all_ids = []
    for day in state.optimized_itinerary:
        for leg in day.get("legs", []):
            all_ids.append(leg["attraction"]["id"])
    assert len(all_ids) == len(set(all_ids)), f"Duplicates found: {all_ids}"


# ---------- 4. Max attractions per day respected ----------
def test_max_attractions_per_day():
    req = _jaipur_request()
    state = PlannerAgent().run(req)
    for day in state.optimized_itinerary:
        count = len(day.get("legs", []))
        assert count <= OptimizationAgent.MAX_ATTRACTIONS_PER_DAY, (
            f"Day {day['day']} has {count} attractions"
        )


# ---------- 5. Requested duration respected ----------
def test_duration_respected():
    for dur in (1, 2, 3, 5):
        req = _jaipur_request(duration=dur)
        state = PlannerAgent().run(req)
        assert len(state.optimized_itinerary) == dur


# ---------- 6. Unavailable accommodation not fabricated ----------
def test_unavailable_accommodation_not_fabricated(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_DATA", "false")
    req = _jaipur_request()
    state = PlannerAgent().run(req)
    assert state.candidate_hotels == []
    for day in state.optimized_itinerary:
        assert day["hotel"] is None
        assert day["hotel_status"] == "unavailable"


def test_default_demo_accommodation_is_included_in_plan_budget(monkeypatch):
    monkeypatch.delenv("WANDERWISE_DEMO_DATA", raising=False)
    monkeypatch.delenv("WANDERWISE_DEMO_HOTELS", raising=False)
    state = PlannerAgent().run(_jaipur_request())

    assert state.candidate_hotels
    assert state.candidate_hotels[0]["source_type"] == "synthetic"
    assert all(day["hotel"] for day in state.optimized_itinerary)
    assert all(day["hotel_status"] == "demo_selected" for day in state.optimized_itinerary)
    assert state.budget_result["accommodation_cost"] == 5000
    assert state.budget_result["demonstration_cost_total"] > 0


def test_all_twenty_demo_destinations_generate_complete_labeled_plans(monkeypatch):
    monkeypatch.delenv("WANDERWISE_DEMO_DATA", raising=False)
    monkeypatch.delenv("WANDERWISE_DEMO_HOTELS", raising=False)
    monkeypatch.delenv("WANDERWISE_DEMO_ATTRACTIONS", raising=False)
    with DEMO_ATTRACTIONS_PATH.open(newline="", encoding="utf-8-sig") as data_file:
        destinations = sorted({row["destination_name"] for row in csv.DictReader(data_file)})

    assert len(destinations) == 20
    for destination in destinations:
        state = PlannerAgent().run(_jaipur_request(
            destination=destination,
            duration=3,
            travelers=2,
            budget=50000,
            interests=["History", "Forts", "Nature", "Religious", "Culture", "Adventure", "Beach"],
        ))
        scheduled_legs = [
            leg
            for day in state.optimized_itinerary
            for leg in day["legs"]
        ]

        assert not state.validation_result.get("error"), destination
        assert len(state.candidate_attractions) == 3, destination
        assert len(scheduled_legs) == 3, destination
        assert state.candidate_hotels[0]["source_type"] == "synthetic", destination
        assert all(day["hotel"] for day in state.optimized_itinerary), destination
        assert all(leg["attraction"]["source_type"] == "synthetic" for leg in scheduled_legs), destination
        assert all(leg["attraction"]["fee_status"] in {"DEMO_FREE", "DEMO_PAID"} for leg in scheduled_legs), destination
        assert all(leg["recommendation_reason"] for leg in scheduled_legs), destination
        assert all(leg["transport"]["status"] == "calculated" for leg in scheduled_legs), destination
        assert state.budget_result["is_estimate_complete"] is True, destination
        assert state.budget_result["data_status"] == "DEMO_SYNTHETIC", destination
        assert state.budget_result["demonstration_cost_total"] > 0, destination
        assert state.budget_result["remaining_budget_is_spendable"] is False, destination
        assert state.constraint_result["status"] == "incomplete", destination


# ---------- 7. Budget correctly calculated ----------
def test_budget_calculation(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_DATA", "false")
    req = _jaipur_request()
    state = PlannerAgent().run(req)
    br = state.budget_result
    available_components = [
        br[key]
        for key in ("accommodation_cost", "attraction_cost", "transport_cost")
        if br[key] is not None
    ]
    if available_components:
        assert abs(br["total_estimated_cost"] - sum(available_components)) < 0.01
        assert abs(br["remaining_budget"] - (req.budget - sum(available_components))) < 0.01
        if not br["total_is_complete"]:
            assert br["remaining_budget_is_spendable"] is False
    else:
        assert br["total_estimated_cost"] is None
        assert br["remaining_budget"] is None
    assert br["total_is_complete"] is False


# ---------- 8. Constraint validation ----------
def test_constraint_validation(monkeypatch):
    monkeypatch.setenv("WANDERWISE_DEMO_DATA", "false")
    req = _jaipur_request()
    state = PlannerAgent().run(req)
    cr = state.constraint_result
    assert "feasible" in cr
    assert "violations" in cr
    # Legacy enrichment has no field-level provenance, so feasibility is not asserted.
    assert cr["status"] == "incomplete"
    assert cr["feasible"] is False
    assert cr["warnings"]


# ---------- 9. Itinerary generation produces legs ----------
def test_itinerary_has_legs():
    req = _jaipur_request()
    state = PlannerAgent().run(req)
    total_legs = sum(len(d.get("legs", [])) for d in state.optimized_itinerary)
    assert total_legs > 0, "Itinerary should contain at least one attraction"


def test_unmatched_interest_uses_verified_destination_attractions():
    req = _jaipur_request(interests=["Quantum Gardening"], duration=2)
    state = PlannerAgent().run(req)
    total_legs = sum(len(day.get("legs", [])) for day in state.optimized_itinerary)
    assert total_legs > 0


# ---------- 10. Invalid destination returns error ----------
def test_invalid_destination():
    req = _jaipur_request(destination="Atlantis")
    state = PlannerAgent().run(req)
    assert state.validation_result.get("error") is not None


# ---------- 11. Empty days explicitly marked ----------
def test_empty_days_marked():
    # 10 days but only 6 attractions → some days should have the note
    req = _jaipur_request(duration=10)
    state = PlannerAgent().run(req)
    empty = [d for d in state.optimized_itinerary if not d.get("legs")]
    for d in empty:
        assert "note" in d
        assert "No eligible" in d["note"]
