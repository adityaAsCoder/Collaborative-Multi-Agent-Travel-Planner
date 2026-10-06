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

    terms = [term.strip().lower() for term in interests if term.strip()]
    text = result[
        ["name", "category", "subcategory", "description"]
    ].astype(str).agg(" ".join, axis=1).str.lower()
    result["_interest_score"] = text.apply(
        lambda value: sum(5 for term in terms if term in value)
    )
    result["_rating_score"] = pd.to_numeric(result["rating"], errors="coerce").fillna(0)
    result["_popularity_score"] = pd.to_numeric(
        result["popularity"], errors="coerce"
    ).fillna(0)
    result["_rank"] = result["_interest_score"] + result["_rating_score"] + (
        result["_popularity_score"] / 100
    )
    return result.sort_values(["_rank", "rating"], ascending=False).drop(
        columns=["_interest_score", "_rating_score", "_popularity_score", "_rank"]
    )


def destination_hotels(
    hotels: pd.DataFrame, destination_id: int, destination_name: str
) -> pd.DataFrame:
    """Return hotels linked by destination id or by an address match."""
    by_id = hotels[hotels["destination_id"].astype(str) == str(destination_id)].copy()
    if not by_id.empty:
        return by_id

    name_terms = [
        term.lower()
        for term in destination_name.replace("(", " ").replace(")", " ").split()
        if len(term) > 3
    ]
    if not name_terms or "address" not in hotels:
        return hotels.iloc[0:0].copy()
    address = hotels["address"].astype(str).str.lower()
    mask = address.apply(lambda value: any(term in value for term in name_terms))
    return hotels.loc[mask].copy()


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
