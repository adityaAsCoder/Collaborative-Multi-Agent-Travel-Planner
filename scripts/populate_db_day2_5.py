"""Idempotently load the processed CSV catalog without deleting saved records."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data.database import SessionLocal, engine
from app.data.models import Attraction, Base, Destination, Hotel
from app.data.quality import address_matches_destination, finite_number

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DESTINATIONS_CSV = ROOT / "datasets" / "processed" / "destinations.csv"
ATTRACTIONS_CSV = ROOT / "datasets" / "processed" / "attractions.csv"
HOTELS_CSV = ROOT / "datasets" / "processed" / "hotels.csv"


def _value(row: pd.Series, key: str) -> Any:
    value = row.get(key)
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _number(
    row: pd.Series,
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    value = finite_number(_value(row, key))
    if value is None:
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _normalized_name(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _destination_map(db: Session, destination_rows: pd.DataFrame) -> dict[int, Destination]:
    result: dict[int, Destination] = {}
    for _, row in destination_rows.iterrows():
        destination_name = str(_value(row, "destination_name") or "").strip()
        if not destination_name:
            raise ValueError("A destination CSV row is missing destination_name.")
        destination = (
            db.query(Destination)
            .filter(func.lower(Destination.destination_name) == destination_name.casefold())
            .first()
        )
        if destination is None:
            requested_id = int(_number(row, "destination_id", minimum=1) or 0)
            if requested_id and db.get(Destination, requested_id) is not None:
                raise ValueError(
                    f"Destination ID {requested_id} is already used by a different destination."
                )
            destination = Destination(
                destination_id=requested_id or None,
                destination_name=destination_name,
            )
            db.add(destination)
            db.flush()

        destination.state = _value(row, "state")
        destination.country = _value(row, "country")
        destination.latitude = _number(row, "latitude", minimum=-90, maximum=90)
        destination.longitude = _number(row, "longitude", minimum=-180, maximum=180)
        destination.source = _value(row, "source")
        destination.source_record_id = _value(row, "source_record_id")
        source_id = int(_number(row, "destination_id", minimum=1) or 0)
        if source_id in result:
            raise ValueError(f"Duplicate destination_id in CSV: {source_id}")
        result[source_id] = destination
    return result


def _read_inputs(
    destinations_path: Path,
    attractions_path: Path,
    hotels_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frames = tuple(
        pd.read_csv(path, keep_default_na=False)
        for path in (destinations_path, attractions_path, hotels_path)
    )
    destinations, attractions, hotels = frames
    for frame, required, name in (
        (destinations, {"destination_id", "destination_name"}, "destinations"),
        (attractions, {"attraction_id", "name", "destination_id"}, "attractions"),
        (hotels, {"hotel_id", "name"}, "hotels"),
    ):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{name}.csv is missing required columns: {sorted(missing)}")
    for frame, key, name in (
        (destinations, "destination_id", "destinations"),
        (attractions, "attraction_id", "attractions"),
        (hotels, "hotel_id", "hotels"),
    ):
        identifiers = pd.to_numeric(frame[key], errors="coerce")
        if identifiers.isna().any() or (identifiers <= 0).any() or identifiers.duplicated().any():
            raise ValueError(f"{name}.csv must contain unique positive {key} values.")
    return destinations, attractions, hotels


def populate_db_idempotent(
    *,
    destinations_path: Path = DESTINATIONS_CSV,
    attractions_path: Path = ATTRACTIONS_CSV,
    hotels_path: Path = HOTELS_CSV,
    session_factory=SessionLocal,
    db_engine=engine,
) -> dict[str, int]:
    """Upsert canonical rows, preserving IDs and saved-trip foreign keys."""
    destinations_frame, attractions_frame, hotels_frame = _read_inputs(
        destinations_path,
        attractions_path,
        hotels_path,
    )
    Base.metadata.create_all(bind=db_engine)
    db = session_factory()
    try:
        destination_map = _destination_map(db, destinations_frame)
        db.query(Attraction).update(
            {Attraction.is_active: False},
            synchronize_session=False,
        )
        attraction_ids: set[int] = set()

        for _, row in attractions_frame.iterrows():
            attraction_id = int(_number(row, "attraction_id", minimum=1) or 0)
            source_destination_id = int(_number(row, "destination_id", minimum=1) or 0)
            destination = destination_map.get(source_destination_id)
            if destination is None:
                raise ValueError(
                    f"Attraction {attraction_id} references unknown destination_id "
                    f"{source_destination_id}."
                )
            name = str(_value(row, "name") or "").strip()
            if not name:
                raise ValueError(f"Attraction {attraction_id} has no name.")
            attraction = db.get(Attraction, attraction_id)
            if attraction is not None and (
                attraction.destination_id != destination.destination_id
                or _normalized_name(attraction.name) != _normalized_name(name)
            ):
                raise ValueError(
                    f"Attraction ID {attraction_id} conflicts with the existing entity "
                    f"{attraction.name!r}; refusing to change saved-trip identity."
                )
            if attraction is None:
                attraction = Attraction(
                    attraction_id=attraction_id,
                    name=name,
                    normalized_name=str(_value(row, "normalized_name") or _normalized_name(name)),
                    destination_id=destination.destination_id,
                )
                db.add(attraction)
            attraction.name = name
            attraction.normalized_name = str(
                _value(row, "normalized_name") or _normalized_name(name)
            )
            attraction.destination_id = destination.destination_id
            attraction.category = _value(row, "category")
            attraction.subcategory = _value(row, "subcategory")
            attraction.latitude = _number(row, "latitude", minimum=-90, maximum=90)
            attraction.longitude = _number(row, "longitude", minimum=-180, maximum=180)
            attraction.rating = _number(row, "rating", minimum=0, maximum=5)
            attraction.rating_validation_status = _value(row, "rating_validation_status")
            attraction.review_count = _number(row, "review_count", minimum=0)
            attraction.estimated_cost = _number(row, "estimated_cost", minimum=0)
            attraction.currency = _value(row, "currency")
            attraction.estimated_visit_duration_min = _number(
                row,
                "estimated_visit_duration_min",
                minimum=1,
            )
            attraction.popularity = _number(row, "popularity", minimum=0)
            attraction.description = _value(row, "description")
            attraction.source = _value(row, "source")
            attraction.source_record_id = _value(row, "source_record_id")
            attraction.source_url = _value(row, "source_url")
            attraction.source_confidence = _value(row, "source_confidence")
            attraction.coordinate_source = _value(row, "coordinate_source")
            attraction.rating_source = _value(row, "rating_source")
            attraction.cost_source = _value(row, "cost_source")
            attraction.cost_validation_status = _value(row, "cost_validation_status")
            attraction.duration_source = _value(row, "duration_source")
            attraction.duration_validation_status = _value(row, "duration_validation_status")
            attraction.coordinate_status = _value(row, "coordinate_status")
            attraction.data_quality_status = _value(row, "data_quality_status")
            attraction.is_active = True
            attraction_ids.add(attraction_id)

        hotel_ids: set[int] = set()
        db_destinations = db.query(Destination).all()
        for _, row in hotels_frame.iterrows():
            hotel_id = int(_number(row, "hotel_id", minimum=1) or 0)
            name = str(_value(row, "name") or "").strip()
            if not name:
                raise ValueError(f"Hotel {hotel_id} has no name.")
            address = str(_value(row, "address") or "").strip()
            matching_destinations = [
                destination
                for destination in db_destinations
                if address_matches_destination(
                    address,
                    destination.destination_name,
                    destination.state,
                )
            ]
            destination_id = (
                matching_destinations[0].destination_id
                if len(matching_destinations) == 1
                else None
            )
            if len(matching_destinations) > 1:
                logger.warning(
                    "Hotel %s matched multiple destination address suffixes; leaving it unlinked.",
                    hotel_id,
                )

            hotel = db.get(Hotel, hotel_id)
            if hotel is not None and (
                _normalized_name(hotel.name) != _normalized_name(name)
                or str(hotel.address or "").strip().casefold() != address.casefold()
            ):
                raise ValueError(
                    f"Hotel ID {hotel_id} conflicts with existing property "
                    f"{hotel.name!r}; refusing to change saved-trip identity."
                )
            if hotel is None:
                hotel = Hotel(
                    hotel_id=hotel_id,
                    name=name,
                    normalized_name=str(_value(row, "normalized_name") or _normalized_name(name)),
                    address=address,
                )
                db.add(hotel)
            hotel.name = name
            hotel.normalized_name = str(
                _value(row, "normalized_name") or _normalized_name(name)
            )
            hotel.address = address
            hotel.destination_id = destination_id
            hotel.latitude = _number(row, "latitude", minimum=-90, maximum=90)
            hotel.longitude = _number(row, "longitude", minimum=-180, maximum=180)
            hotel.price_per_night = _number(row, "price_per_night", minimum=0.01)
            hotel.price_source = _value(row, "price_source")
            hotel.price_source_url = _value(row, "price_source_url")
            hotel.price_validation_status = _value(row, "price_validation_status")
            hotel.currency = _value(row, "currency")
            hotel.rating = _number(row, "rating", minimum=0, maximum=5)
            hotel.rating_source = _value(row, "rating_source")
            hotel.rating_validation_status = _value(row, "rating_validation_status")
            hotel.review_count = _number(row, "review_count", minimum=0)
            hotel.room_type = _value(row, "room_type")
            amenities = _value(row, "amenities")
            if isinstance(amenities, str):
                try:
                    amenities = json.loads(amenities)
                except json.JSONDecodeError:
                    raise ValueError(f"Hotel {hotel_id} contains invalid amenities JSON.") from None
            hotel.amenities = amenities
            hotel.source = _value(row, "source")
            hotel.source_record_id = _value(row, "source_record_id")
            hotel.source_url = _value(row, "source_url")
            hotel.provenance_source = _value(row, "provenance_source")
            hotel.data_quality_status = _value(row, "data_quality_status")
            hotel_ids.add(hotel_id)

        db.commit()
        result = {
            "destinations_upserted": len(destination_map),
            "attractions_activated": len(attraction_ids),
            "hotels_upserted": len(hotel_ids),
            "inactive_attractions_preserved": (
                db.query(Attraction).filter(Attraction.is_active.is_(False)).count()
            ),
        }
        logger.info("Processed CSV import completed: %s", result)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_db_idempotent()
