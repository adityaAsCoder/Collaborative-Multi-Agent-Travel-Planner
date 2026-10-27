"""CSV-backed catalog and recommendation helpers for the end-user application."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.data.preferences import matched_interests
from app.data.quality import address_matches_destination, verified_measure

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "datasets" / "processed"
AUTH_DB = PROJECT_ROOT / "travel_planner.db"


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Required dataset is missing: {path}")
    return pd.read_csv(path).fillna("")


def load_catalog() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three user-facing catalog datasets."""
    return (
        _read_csv("destinations.csv"),
        _read_csv("attractions.csv"),
        _read_csv("hotels.csv"),
    )


def search_destinations(destinations: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return relevant destinations, matching names, regions, and countries."""
    query = query.strip().lower()
    if not query:
        return destinations.copy()
    searchable = destinations[
        ["destination_name", "state", "country"]
    ].astype(str).agg(" ".join, axis=1).str.lower()
    return destinations.loc[searchable.str.contains(query, na=False, regex=False)].copy()


def destination_attractions(
    attractions: pd.DataFrame, destination_id: int, interests: Iterable[str] = ()
) -> pd.DataFrame:
    """Rank attractions for a destination using user interests and quality signals."""
    result = attractions[attractions["destination_id"].astype(str) == str(destination_id)].copy()
    if result.empty:
        return result

    estimated = result.get(
        "data_quality_status", pd.Series("", index=result.index)
    ).astype(str).str.casefold().str.contains("estimate", na=False)
    no_source_url = ~result.get(
        "source_url", pd.Series("", index=result.index)
    ).fillna("").astype(str).str.strip().ne("")
    unverified_metadata = estimated | no_source_url
    for field in ("category", "subcategory", "description"):
        if field in result:
            result.loc[unverified_metadata, field] = None
    requested_interests = [str(term).strip() for term in interests if str(term).strip()]
    matched = result.apply(
        lambda row: matched_interests(row.to_dict(), requested_interests),
        axis=1,
    )
    result["_matched_interests"] = matched
    result["_interest_score"] = matched.map(len)
    result["_verified_rating"] = result.apply(
        lambda row: verified_measure(
            row.get("rating"),
            row.get("rating_source"),
            minimum=0,
            maximum=5,
            validation_status=row.get("rating_validation_status"),
        ) or 0,
        axis=1,
    )
    result["_rank"] = result["_interest_score"] * 10 + result["_verified_rating"]
    result["_recommendation_reason"] = result["_matched_interests"].map(
        lambda values: (
            f"Matched interests: {', '.join(values)}."
            if values
            else "Fallback: no selected interest matched the available attraction text."
        )
    )
    result["rating"] = result.apply(
        lambda row: verified_measure(
            row.get("rating"),
            row.get("rating_source"),
            minimum=0,
            maximum=5,
            validation_status=row.get("rating_validation_status"),
        ),
        axis=1,
    )
    result["estimated_cost"] = result.apply(
        lambda row: verified_measure(
            row.get("estimated_cost"),
            row.get("cost_source"),
            minimum=0,
            validation_status=row.get("cost_validation_status"),
        ),
        axis=1,
    )
    result["estimated_visit_duration_min"] = result.apply(
        lambda row: verified_measure(
            row.get("estimated_visit_duration_min"),
            row.get("duration_source"),
            minimum=1,
            validation_status=row.get("duration_validation_status"),
        ),
        axis=1,
    )
    ranked = result.sort_values(
        ["_rank", "_verified_rating", "name"],
        ascending=[False, False, True],
    )
    return ranked.drop(columns=["_interest_score", "_verified_rating", "_rank"])


def destination_hotels(
    hotels: pd.DataFrame, destination_id: int, destination_name: str
) -> pd.DataFrame:
    """Return hotels linked by destination id or by an address match."""
    if "address" not in hotels:
        return hotels.iloc[0:0].copy()
    address_matches = hotels["address"].apply(
        lambda address: address_matches_destination(address, destination_name)
    )
    by_id = hotels["destination_id"].astype(str) == str(destination_id)
    has_address = hotels["address"].fillna("").astype(str).str.strip().ne("")
    return hotels.loc[address_matches | (by_id & ~has_address)].copy()


def build_itinerary(
    attractions: pd.DataFrame, duration: int, max_per_day: int = 4
) -> list[dict]:
    """Distribute ranked attractions across days without repeating a place."""
    if attractions.empty or duration <= 0:
        return [{"day": day, "attractions": []} for day in range(1, duration + 1)]
    selected = attractions.head(duration * max_per_day).to_dict("records")
    days = [{"day": day, "attractions": []} for day in range(1, duration + 1)]
    for index, attraction in enumerate(selected):
        days[index % duration]["attractions"].append(attraction)
    return days


def _password_digest(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def init_auth_db() -> None:
    """Create the local account table without changing existing travel tables."""
    with sqlite3.connect(AUTH_DB) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_digest TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_hash TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_user(email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if "@" not in email or len(password) < 8:
        return False, "Use a valid email and a password with at least 8 characters."
    init_auth_db()
    try:
        with sqlite3.connect(AUTH_DB) as connection:
            connection.execute(
                "INSERT INTO app_users(email, password_digest) VALUES (?, ?)",
                (email, _password_digest(password)),
            )
        return True, "Account created."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."


def verify_user(email: str, password: str) -> bool:
    init_auth_db()
    with sqlite3.connect(AUTH_DB) as connection:
        row = connection.execute(
            "SELECT password_digest FROM app_users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if not row:
        return False
    salt_hex, digest_hex = row[0].split("$", 1)
    expected = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), 120_000
    ).hex()
    return hmac.compare_digest(expected, digest_hex)
