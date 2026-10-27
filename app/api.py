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
import hashlib
import ipaddress
import os
import secrets
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import sys

# Make sure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.data.catalog import create_user, verify_user, init_auth_db, AUTH_DB
from app.data.database import SessionLocal
from app.data.models import Destination
from app.schemas.planning import PlanningRequest
from app.agents.implementations import PlannerAgent
from app.providers.hotels import (
    ExpediaRapidClient,
    HotelProviderError,
    HotelProviderNotConfigured,
    HotelProviderRateLimited,
    HotelProviderUnavailable,
    hotel_mode,
    validate_stay,
)


app = FastAPI(title="WanderWise Travel Planner API", version="1.0.0")

SESSION_COOKIE = "wanderwise_session"
CSRF_COOKIE = "wanderwise_csrf"
CSRF_HEADER = "X-CSRF-Token"
SESSION_TTL = timedelta(hours=12)
RATE_LIMIT_WINDOW = timedelta(
    seconds=int(os.environ.get("WANDERWISE_LOGIN_RATE_WINDOW_SECONDS", "900"))
)
RATE_LIMIT_MAX_FAILURES = int(
    os.environ.get("WANDERWISE_LOGIN_RATE_MAX_FAILURES", "5")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "WANDERWISE_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", CSRF_HEADER],
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_hash TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                attempt_key TEXT PRIMARY KEY,
                failed_count INTEGER NOT NULL,
                window_started_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_hotel_offers (
                offer_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                provider TEXT NOT NULL,
                offer_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
        """)


def _session_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_session(email: str) -> str:
    init_auth_db()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    with sqlite3.connect(AUTH_DB) as conn:
        conn.execute(
            "INSERT INTO auth_sessions(session_hash, email, expires_at) VALUES (?, ?, ?)",
            (_session_hash(token), email, expires_at.isoformat()),
        )
    return token


def _normalized_email(email: str) -> str:
    return email.strip().casefold()


def _rate_limit_key(email: str, request: Request | None) -> str:
    client_host = request.client.host if request and request.client else "unknown"
    return f"{_normalized_email(email)}|{client_host}"


def _check_login_rate_limit(email: str, request: Request | None) -> str:
    init_trips_table()
    key = _rate_limit_key(email, request)
    now = datetime.now(timezone.utc)
    with sqlite3.connect(AUTH_DB) as conn:
        row = conn.execute(
            "SELECT failed_count, window_started_at FROM login_attempts WHERE attempt_key = ?",
            (key,),
        ).fetchone()
    if not row:
        return key
    try:
        started = datetime.fromisoformat(row[1])
    except (TypeError, ValueError):
        started = now
    if now - started >= RATE_LIMIT_WINDOW:
        with sqlite3.connect(AUTH_DB) as conn:
            conn.execute("DELETE FROM login_attempts WHERE attempt_key = ?", (key,))
        return key
    if row[0] >= RATE_LIMIT_MAX_FAILURES:
        retry_after = max(1, int((RATE_LIMIT_WINDOW - (now - started)).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    return key


def _record_login_failure(key: str) -> None:
    now = datetime.now(timezone.utc)
    with sqlite3.connect(AUTH_DB) as conn:
        conn.execute(
            """
            INSERT INTO login_attempts(attempt_key, failed_count, window_started_at)
            VALUES (?, 1, ?)
            ON CONFLICT(attempt_key) DO UPDATE SET failed_count = failed_count + 1
            """,
            (key, now.isoformat()),
        )


def _clear_login_failures(key: str) -> None:
    with sqlite3.connect(AUTH_DB) as conn:
        conn.execute("DELETE FROM login_attempts WHERE attempt_key = ?", (key,))


def _csrf_token_from_cookie(token: str | None) -> str:
    return token or secrets.token_urlsafe(32)


def _set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        secure=os.environ.get("WANDERWISE_COOKIE_SECURE", "").casefold() == "true",
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
    )


def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
) -> None:
    allowed_origins = {
        origin.strip()
        for origin in os.environ.get(
            "WANDERWISE_ALLOWED_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    }
    origin = request.headers.get("origin")
    if origin and origin not in allowed_origins:
        raise HTTPException(status_code=403, detail="Request origin is not trusted.")
    header = request.headers.get(CSRF_HEADER)
    if not csrf_cookie or not header or not secrets.compare_digest(csrf_cookie, header):
        raise HTTPException(status_code=403, detail="CSRF token is missing or invalid.")


def _authenticated_email(session_token: str | None) -> str:
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    init_auth_db()
    with sqlite3.connect(AUTH_DB) as conn:
        row = conn.execute(
            "SELECT email, expires_at FROM auth_sessions WHERE session_hash = ?",
            (_session_hash(session_token),),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    try:
        expires_at = datetime.fromisoformat(row[1])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Authentication session is invalid.")
    if expires_at <= datetime.now(timezone.utc):
        with sqlite3.connect(AUTH_DB) as conn:
            conn.execute("DELETE FROM auth_sessions WHERE session_hash = ?", (_session_hash(session_token),))
        raise HTTPException(status_code=401, detail="Authentication session has expired.")
    return row[0]


def current_email(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> str:
    return _authenticated_email(session_token)


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
    destination: str
    duration: int
    travelers: int
    budget: float
    currency: str = "INR"
    interests: List[str]
    max_daily_travel_time: Optional[int] = None
    accommodation_preference: str = "any"


class SaveTripRequest(BaseModel):
    request: dict
    result: dict


class HotelSearchRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=120)
    check_in: str
    check_out: str
    adults: int = Field(ge=1, le=16)
    rooms: int = Field(default=1, ge=1, le=8)
    child_ages: list[int] = Field(default_factory=list, max_length=16)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")

    @field_validator("check_out")
    @classmethod
    def dates_are_valid(cls, check_out: str, info):
        check_in = info.data.get("check_in")
        if check_in:
            validate_stay(check_in, check_out)
        return check_out

    @field_validator("child_ages")
    @classmethod
    def valid_child_ages(cls, ages: list[int]) -> list[int]:
        if any(age < 0 or age > 17 for age in ages):
            raise ValueError("Child ages must be between 0 and 17.")
        return ages


# ──────────────────────────── Helpers ────────────────────────────────────────

def _serialize_state(state) -> dict:
    """Convert PlanningState → plain dict safe for JSON."""
    def serialize_transport(route: dict | None) -> dict | None:
        if route is None:
            return None
        return {
            "origin": route.get("origin"),
            "destination": route.get("destination"),
            "origin_id": route.get("origin_id"),
            "destination_id": route.get("destination_id"),
            "distance_km": route.get("distance_km"),
            "time_min": route.get("time_min"),
            "cost": route.get("cost"),
            "cost_per_km": route.get("cost_per_km"),
            "status": route.get("status", "unavailable"),
            "method": route.get("method"),
            "mode": route.get("mode"),
            "data_status": route.get("data_status"),
            "source_type": route.get("source_type"),
            "reason": route.get("reason"),
        }

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
                    "category": att.get("category"),
                    "subcategory": att.get("subcategory"),
                    "cost": att.get("cost"),
                    "cost_basis": att.get("cost_basis", "per_person"),
                    "cost_data_status": att.get("cost_data_status", "unknown"),
                    "fee_status": att.get("fee_status"),
                    "data_status": att.get("data_status"),
                    "source_type": att.get("source_type"),
                    "duration": att.get("duration"),
                    "rating": att.get("rating"),
                    "latitude": att.get("latitude"),
                    "longitude": att.get("longitude"),
                    "coordinate_status": att.get("coordinate_status"),
                    "coordinate_reason": att.get("coordinate_reason"),
                },
                "transport": serialize_transport(tr),
                "recommendation_reason": leg.get("recommendation_reason"),
            })
        itinerary.append({
            "day": day["day"],
            "hotel": day.get("hotel"),
            "hotel_status": day.get("hotel_status", "unavailable"),
            "hotel_reason": day.get("hotel_reason"),
            "return_transport": serialize_transport(day.get("return_transport")),
            "note": day.get("note", ""),
            "unscheduled_attractions": day.get("unscheduled_attractions", []),
            "legs": legs,
        })

    preference_score = sum(state.preference_scores.values())
    accommodation_details = state.budget_result.get("accommodation", {})
    accommodation = {
        **state.accommodation_result,
        **accommodation_details,
    }
    return {
        "request": state.planning_request.model_dump() if state.planning_request else {},
        "itinerary": itinerary,
        "candidate_hotels": state.candidate_hotels,
        "accommodation": accommodation,
        "budget": state.budget_result,
        "constraints": state.constraint_result,
        "preference_score": preference_score,
        "planning_note": state.planning_note,
        "validation_error": state.validation_result.get("error") if state.validation_result else None,
    }


# ──────────────────────────── Routes ─────────────────────────────────────────

@app.get("/auth/csrf")
def csrf_token(
    response: Response,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
):
    token = _csrf_token_from_cookie(csrf_cookie)
    _set_csrf_cookie(response, token)
    return {"csrf_token": token}


@app.post("/auth/register", dependencies=[Depends(require_csrf)])
def register(body: RegisterRequest):
    ok, msg = create_user(body.email, body.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/auth/login", dependencies=[Depends(require_csrf)])
def login(
    body: LoginRequest,
    request: Request = None,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
):
    email = body.email.strip().lower()
    attempt_key = _check_login_rate_limit(email, request)
    if not verify_user(email, body.password):
        _record_login_failure(attempt_key)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _clear_login_failures(attempt_key)
    token = _create_session(email)
    response = Response(content=json.dumps({"email": email, "message": "Login successful."}), media_type="application/json")
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=os.environ.get("WANDERWISE_COOKIE_SECURE", "").casefold() == "true",
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
    )
    _set_csrf_cookie(response, csrf_cookie or secrets.token_urlsafe(32))
    return response


@app.post("/auth/logout", dependencies=[Depends(require_csrf)])
def logout(response: Response, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    if session_token:
        with sqlite3.connect(AUTH_DB) as conn:
            conn.execute("DELETE FROM auth_sessions WHERE session_hash = ?", (_session_hash(session_token),))
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "Logged out."}


@app.get("/auth/me")
def me(email: str = Depends(current_email)):
    return {"email": email}


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


def _client_ip(request: Request) -> str | None:
    host = request.client.host if request.client else ""
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


@app.post("/hotels/search", dependencies=[Depends(require_csrf)])
def search_live_hotels(
    body: HotelSearchRequest,
    request: Request,
    email: str = Depends(current_email),
):
    init_trips_table()
    try:
        if hotel_mode() != "live":
            raise HTTPException(
                status_code=503,
                detail="Live hotel search is disabled. Set WANDERWISE_HOTEL_MODE=live to use Expedia Rapid.",
            )
        search_result = asyncio.run(ExpediaRapidClient().search(
            destination=body.destination,
            check_in=body.check_in,
            check_out=body.check_out,
            adults=body.adults,
            rooms=body.rooms,
            child_ages=body.child_ages,
            currency=body.currency,
            session_id=str(uuid.uuid4()),
            customer_ip=_client_ip(request),
        ))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LookupError as error:
        return {
            "provider": "expedia_rapid",
            "status": "no_results",
            "offers": [],
            "message": str(error),
        }
    except HotelProviderNotConfigured as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except HotelProviderRateLimited as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except HotelProviderUnavailable as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except HotelProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    created_at = datetime.now(timezone.utc)
    public_offers = []
    with sqlite3.connect(AUTH_DB) as conn:
        for offer in search_result["offers"]:
            offer_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO user_hotel_offers
                    (offer_id, email, provider, offer_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    offer_id,
                    email,
                    "expedia_rapid",
                    json.dumps(offer),
                    created_at.isoformat(),
                    offer.get("offer_expires_at"),
                ),
            )
            public_offers.append({
                key: value for key, value in offer.items()
                if not key.startswith("_")
            } | {"offer_id": offer_id})
    return {
        key: value for key, value in search_result.items() if key != "offers"
    } | {"offers": public_offers}


@app.post(
    "/hotel-offers/{offer_id}/price-check",
    dependencies=[Depends(require_csrf)],
)
def price_check_hotel_offer(
    offer_id: str,
    request: Request,
    email: str = Depends(current_email),
):
    init_trips_table()
    with sqlite3.connect(AUTH_DB) as conn:
        row = conn.execute(
            """
            SELECT offer_json, expires_at FROM user_hotel_offers
            WHERE offer_id = ? AND email = ? AND provider = 'expedia_rapid'
            """,
            (offer_id, email),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Hotel offer not found.")
    offer = json.loads(row[0])
    expires_at = row[1]
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=410,
                    detail="This hotel offer has expired. Search again for current availability.",
                )
        except ValueError as error:
            raise HTTPException(status_code=410, detail="The hotel offer expiry is invalid.") from error
    try:
        result = asyncio.run(ExpediaRapidClient().price_check(
            offer["_price_check_path"],
            session_id=str(uuid.uuid4()),
            customer_ip=_client_ip(request),
        ))
    except HotelProviderNotConfigured as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except HotelProviderRateLimited as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except HotelProviderUnavailable as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except HotelProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        "provider": "expedia_rapid",
        "status": result["status"],
        "hotel_name": offer.get("hotel_name"),
        "check_in": offer.get("check_in"),
        "check_out": offer.get("check_out"),
        "currency": offer.get("currency"),
        "original_total": offer.get("total_price"),
        "current_pricing": result.get("occupancy_pricing"),
        "message": (
            "Current price and availability verified by Expedia Rapid."
            if result["status"] == "available"
            else "The selected rate changed or is no longer available. Search again before booking."
        ),
        "booking_api_available": bool((result.get("links") or {}).get("book")),
    }


@app.post("/plan", dependencies=[Depends(require_csrf)])
def plan_trip(body: PlanRequest, email: str = Depends(current_email)):

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


@app.post("/trips", dependencies=[Depends(require_csrf)])
def save_trip_endpoint(body: SaveTripRequest, email: str = Depends(current_email)):
    trip_id = save_trip(email, body.request, body.result)
    return {"trip_id": trip_id, "message": "Trip saved successfully."}

@app.get("/trips")
def trip_history(email: str = Depends(current_email)):
    return get_trips(email)

@app.get("/trips/{trip_id}")
def trip_detail(trip_id: int, email: str = Depends(current_email)):
    trip = get_trip_by_id(trip_id, email)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return trip


@app.get("/health")
def health():
    return {"status": "ok"}
