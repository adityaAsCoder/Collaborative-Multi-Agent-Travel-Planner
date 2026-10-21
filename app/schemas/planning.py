from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class PlanningRequest(BaseModel):
    destination: str
    duration: int = Field(gt=0, description="Duration in days must be greater than 0")
    travelers: int = Field(gt=0, description="Number of travelers must be greater than 0")
    budget: float = Field(ge=0, description="Budget must be non-negative")
    currency: str = "INR"
    interests: List[str]
    max_daily_travel_time: Optional[int] = Field(None, gt=0, description="Maximum daily travel time in minutes")
    accommodation_preference: str = Field(pattern="^(budget|standard|luxury|any)$", description="Preference: budget, standard, luxury, or any")

    @field_validator('interests')
    def validate_interests(cls, v):
        if not v:
            raise ValueError('Interests list cannot be empty')
        return v
    
    @field_validator('duration')
    def validate_duration(cls, v):
        if v <= 0:
            raise ValueError('Duration must be > 0')
        return v

    @field_validator('travelers')
    def validate_travelers(cls, v):
        if v <= 0:
            raise ValueError('Travelers must be > 0')
        return v

    @field_validator('budget')
    def validate_budget(cls, v):
        if v < 0:
            raise ValueError('Budget must be >= 0')
        return v

class PlanningState(BaseModel):
    request_id: Optional[int] = None
    planning_request: Optional[PlanningRequest] = None
    candidate_attractions: List[dict] = Field(default_factory=list)
    preference_scores: dict = Field(default_factory=dict)
    candidate_hotels: List[dict] = Field(default_factory=list)
    accommodation_result: dict = Field(default_factory=dict)
    transport_segments: List[dict] = Field(default_factory=list)
    budget_result: dict = Field(default_factory=dict)
    constraint_result: dict = Field(default_factory=dict)
    candidate_itinerary: List[dict] = Field(default_factory=list)
    optimized_itinerary: List[dict] = Field(default_factory=list)
    validation_result: dict = Field(default_factory=dict)
    agent_execution_log: List[dict] = Field(default_factory=list)
    planning_note: Optional[str] = None
    replanning_required: bool = False
