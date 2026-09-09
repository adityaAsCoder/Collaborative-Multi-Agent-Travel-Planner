import pytest
from pydantic import ValidationError
from app.schemas.planning import PlanningRequest, PlanningState

def test_planning_request_valid():
    req = PlanningRequest(
        destination="Udaipur",
        duration=4,
        travelers=2,
        budget=25000,
        interests=["historical", "nature", "culture"],
        max_daily_travel_time=120,
        accommodation_preference="budget"
    )
    assert req.destination == "Udaipur"
    assert req.duration == 4

def test_planning_request_invalid_duration():
    with pytest.raises(ValidationError):
        PlanningRequest(
            destination="Udaipur",
            duration=0,
            travelers=2,
            budget=25000,
            interests=["historical"],
            accommodation_preference="budget"
        )

def test_planning_request_invalid_travelers():
    with pytest.raises(ValidationError):
        PlanningRequest(
            destination="Udaipur",
            duration=4,
            travelers=0,
            budget=25000,
            interests=["historical"],
            accommodation_preference="budget"
        )

def test_planning_request_invalid_budget():
    with pytest.raises(ValidationError):
        PlanningRequest(
            destination="Udaipur",
            duration=4,
            travelers=2,
            budget=-500,
            interests=["historical"],
            accommodation_preference="budget"
        )

def test_planning_request_invalid_preference():
    with pytest.raises(ValidationError):
        PlanningRequest(
            destination="Udaipur",
            duration=4,
            travelers=2,
            budget=25000,
            interests=["historical"],
            accommodation_preference="invalid_pref" # invalid
        )
