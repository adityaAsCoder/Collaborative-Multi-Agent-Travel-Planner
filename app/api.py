"""
FastAPI backend — wraps the existing PlannerAgent, catalog, and auth.

Endpoints:
  POST /auth/register
  POST /auth/login
  GET  /destinations
  POST /plan
  GET  /trips/{user_email}
"""
from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys

# Make sure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.data.catalog import create_user, verify_user, init_auth_db, AUTH_DB
from app.data.database import SessionLocal
from app.data.models import Destination
from app.schemas.planning import PlanningRequest
from app.agents.implementations import PlannerAgent


app = FastAPI(title="WanderWise Travel Planner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────── Trips persistence ──────────────────────────────

def init_trips_table() -> None:
    """Add trips table to existing auth DB without touching travel tables."""
    with sqlite3.connect(AUTH_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_trips (
                trip_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                email     TEXT    NOT NULL,
                request   TEXT    NOT NULL,   -- JSON
                result    TEXT    NOT NULL,   -- JSON
                created_at TEXT  NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_trip(email: str, request_dict: dict, result_dict: dict) -> int:
    init_trips_table()
    with sqlite3.connect(AUTH_DB) as conn:
        cur = conn.execute(
            "INSERT INTO user_trips(email, request, result) VALUES (?,?,?)",
            (email.lower(), json.dumps(request_dict), json.dumps(result_dict)),
        )
        return cur.lastrowid


def get_trips(email: str) -> list[dict]:
    init_trips_table()
    with sqlite3.connect(AUTH_DB) as conn:
        rows = conn.execute(
            "SELECT trip_id, request, result, created_at FROM user_trips WHERE email=? ORDER BY created_at DESC",
            (email.lower(),),
        ).fetchall()
    return [
        {"trip_id": r[0], "request": json.loads(r[1]), "result": json.loads(r[2]), "created_at": r[3]}
        for r in rows
    ]


def get_trip_by_id(trip_id: int, email: str) -> dict | None:
    init_trips_table()
    with sqlite3.connect(AUTH_DB) as conn:
        row = conn.execute(
            "SELECT trip_id, request, result, created_at FROM user_trips WHERE trip_id=? AND email=?",
            (trip_id, email.lower()),
        ).fetchone()
    if not row:
        return None
    return {"trip_id": row[0], "request": json.loads(row[1]), "result": json.loads(row[2]), "created_at": row[3]}


# ──────────────────────────── Pydantic schemas ───────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class PlanRequest(BaseModel):
    email: str
    destination: str
    duration: int
    travelers: int
    budget: float
    currency: str = "INR"
    interests: List[str]
    max_daily_travel_time: Optional[int] = None
    accommodation_preference: str = "any"


class SaveTripRequest(BaseModel):
    email: str
    request: dict
    result: dict


# ──────────────────────────── Helpers ────────────────────────────────────────

def _serialize_state(state) -> dict:
    """Convert PlanningState → plain dict safe for JSON."""
    itinerary = []
    for day in state.optimized_itinerary:
        legs = []
        for leg in day.get("legs", []):
            att = leg["attraction"]
            tr = leg["transport"]
            legs.append({
                "attraction": {
                    "id": att["id"],
                    "name": att["name"],
                    "category": att.get("category") or "",
                    "subcategory": att.get("subcategory") or "",
                    "cost": att.get("cost") or 0,
                    "duration": att.get("duration") or 0,
                    "rating": att.get("rating") or 0,
                    "latitude": att.get("latitude"),
                    "longitude": att.get("longitude"),
                },
                "transport": {
                    "distance_km": tr.get("distance_km", 0),
                    "time_min": tr.get("time_min", 0),
                    "cost": tr.get("cost", 0),
                    "status": tr.get("status", "unavailable"),
                },
            })
        itinerary.append({
            "day": day["day"],
            "hotel": day.get("hotel"),
            "hotel_status": day.get("hotel_status", "unavailable"),
            "note": day.get("note", ""),
            "legs": legs,
        })

    preference_score = sum(state.preference_scores.values())
    has_legs = any(day["legs"] for day in itinerary)
    planning_note = None
    if has_legs and preference_score == 0:
        planning_note = (
            "No exact interest match was found, so the itinerary uses the "
            "highest-rated verified attractions for this destination."
        )
    return {
        "request": state.planning_request.model_dump() if state.planning_request else {},
        "itinerary": itinerary,
        "candidate_hotels": state.candidate_hotels,
        "budget": state.budget_result,
        "constraints": state.constraint_result,
        "preference_score": preference_score,
        "planning_note": planning_note,
        "validation_error": state.validation_result.get("error") if state.validation_result else None,
    }


# ──────────────────────────── Routes ─────────────────────────────────────────

@app.post("/auth/register")
def register(body: RegisterRequest):
    ok, msg = create_user(body.email, body.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/auth/login")
def login(body: LoginRequest):
    if not verify_user(body.email, body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"email": body.email.strip().lower(), "message": "Login successful."}


@app.get("/destinations")
def list_destinations(search: str = ""):
    db = SessionLocal()
    try:
        dests = db.query(Destination).all()
        result = []
        for d in dests:
            if search.lower() in d.destination_name.lower() or not search:
                result.append({
                    "id": d.destination_id,
                    "name": d.destination_name,
                    "state": d.state or "",
                    "country": d.country or "",
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                })
        return result
    finally:
        db.close()


@app.post("/plan")
def plan_trip(body: PlanRequest):
    if not verify_user(body.email, ""):
        # verify_user checks password — we need a token-free way to authorize.
        # Since we have no JWT, we trust the caller's email (session managed in Streamlit).
        pass

    try:
        req = PlanningRequest(
            destination=body.destination,
            duration=body.duration,
            travelers=body.travelers,
            budget=body.budget,
            currency=body.currency,
            interests=body.interests,
            max_daily_travel_time=body.max_daily_travel_time,
            accommodation_preference=body.accommodation_preference,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    agent = PlannerAgent()
    state = agent.run(req)
    result = _serialize_state(state)

    return result


@app.post("/trips")
def save_trip_endpoint(body: SaveTripRequest):
    if not body.email.strip():
        raise HTTPException(status_code=400, detail="A signed-in email is required.")
    trip_id = save_trip(body.email, body.request, body.result)
    return {"trip_id": trip_id, "message": "Trip saved successfully."}


@app.get("/trips/{email}")
def trip_history(email: str):
    return get_trips(email)


@app.get("/trips/{email}/{trip_id}")
def trip_detail(email: str, trip_id: int):
    trip = get_trip_by_id(trip_id, email)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return trip


@app.get("/health")
def health():
    return {"status": "ok"}
