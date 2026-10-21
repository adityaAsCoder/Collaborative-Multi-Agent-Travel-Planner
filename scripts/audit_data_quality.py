"""Generate a read-only data-quality report for every database destination."""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.database import SessionLocal
from app.data.models import Attraction, Destination, Hotel
from app.data.quality import (
    address_matches_destination,
    verified_coordinates,
    verified_measure,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "data_inspection" / "data_quality_audit.md"
MIN_ATTRACTIONS_FOR_SIX_DAYS = 6


def _field(record: Any, name: str, default: Any = None) -> Any:
    return getattr(record, name, default)


def _percent(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%" if denominator else "n/a"


def _csv_snapshot() -> dict:
    path = ROOT / "datasets" / "processed" / "attractions.csv"
    if not path.exists():
        return {"rows": 0, "verified_coordinates": 0, "verified_fees": 0, "verified_durations": 0}
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    return {
        "rows": len(rows),
        "verified_coordinates": sum(
            verified_coordinates(
                row.get("latitude"),
                row.get("longitude"),
                row.get("coordinate_source"),
                row.get("coordinate_status"),
            ) is not None
            for row in rows
        ),
        "verified_fees": sum(
            verified_measure(
                row.get("estimated_cost"), row.get("cost_source"), minimum=0
            ) is not None
            for row in rows
        ),
        "verified_durations": sum(
            verified_measure(
                row.get("estimated_visit_duration_min"),
                row.get("duration_source"),
                minimum=1,
            ) is not None
            for row in rows
        ),
        "verified_ratings": sum(
            verified_measure(
                row.get("rating"),
                row.get("rating_source"),
                minimum=0,
                maximum=5,
                validation_status=row.get("rating_validation_status"),
            ) is not None
            for row in rows
        ),
    }


def generate_report() -> Path:
    db = SessionLocal()
    try:
        destinations = db.query(Destination).order_by(Destination.destination_name).all()
        attractions = db.query(Attraction).filter(Attraction.is_active.is_(True)).all()
        hotels = db.query(Hotel).all()
        attraction_groups: dict[tuple[int | None, str], int] = Counter()
        hotel_groups: dict[tuple[str, str], int] = Counter()

        for attraction in attractions:
            key = (
                _field(attraction, "destination_id"),
                str(_field(attraction, "normalized_name") or _field(attraction, "name") or "").casefold().strip(),
            )
            attraction_groups[key] += 1
        for hotel in hotels:
            key = (
                str(_field(hotel, "normalized_name") or _field(hotel, "name") or "").casefold().strip(),
                str(_field(hotel, "address") or "").casefold().strip(),
            )
            hotel_groups[key] += 1
        duplicate_attractions = sum(count - 1 for count in attraction_groups.values() if count > 1)
        duplicate_hotels = sum(count - 1 for count in hotel_groups.values() if count > 1)

        rows = []
        for destination in destinations:
            destination_attractions = [
                attraction for attraction in attractions
                if _field(attraction, "destination_id") == _field(destination, "destination_id")
            ]
            linked_hotels = []
            for hotel in hotels:
                if (
                    _field(hotel, "destination_id") == _field(destination, "destination_id")
                    or address_matches_destination(
                        _field(hotel, "address"),
                        _field(destination, "destination_name", ""),
                        _field(destination, "state"),
                    )
                ):
                    linked_hotels.append(hotel)

            valid_coordinates = sum(
                verified_coordinates(
                    _field(attraction, "latitude"),
                    _field(attraction, "longitude"),
                    _field(attraction, "coordinate_source"),
                    _field(attraction, "coordinate_status"),
                    _field(destination, "latitude"),
                    _field(destination, "longitude"),
                ) is not None
                for attraction in destination_attractions
            )
            verified_fees = sum(
                verified_measure(
                    _field(attraction, "estimated_cost"),
                    _field(attraction, "cost_source"),
                    minimum=0,
                    validation_status=_field(attraction, "cost_validation_status"),
                ) is not None
                for attraction in destination_attractions
            )
            verified_durations = sum(
                verified_measure(
                    _field(attraction, "estimated_visit_duration_min"),
                    _field(attraction, "duration_source"),
                    minimum=1,
                    validation_status=_field(attraction, "duration_validation_status"),
                ) is not None
                for attraction in destination_attractions
            )
            valid_ratings = sum(
                verified_measure(
                    _field(attraction, "rating"),
                    _field(attraction, "rating_source"),
                    minimum=0,
                    maximum=5,
                    validation_status=_field(attraction, "rating_validation_status"),
                ) is not None
                for attraction in destination_attractions
            )
            categorized_attractions = sum(
                bool(_field(attraction, "category") or _field(attraction, "subcategory"))
                for attraction in destination_attractions
            )
            preference_eligible = sum(
                bool(" ".join(str(value) for value in (
                    _field(attraction, "name"),
                    _field(attraction, "category"),
                    _field(attraction, "subcategory"),
                    _field(attraction, "description"),
                ) if value).strip())
                for attraction in destination_attractions
            )
            valid_hotels = [
                hotel for hotel in linked_hotels
                if verified_coordinates(
                    _field(hotel, "latitude"),
                    _field(hotel, "longitude"),
                    _field(hotel, "provenance_source") or _field(hotel, "source_url"),
                    _field(hotel, "data_quality_status"),
                    _field(destination, "latitude"),
                    _field(destination, "longitude"),
                ) is not None
            ]
            priced_hotels = [
                hotel for hotel in valid_hotels
                if verified_measure(
                    _field(hotel, "price_per_night"),
                    _field(hotel, "price_source"),
                    minimum=0.01,
                    validation_status=_field(hotel, "price_validation_status"),
                ) is not None
            ]
            valid_hotel_ratings = sum(
                verified_measure(
                    _field(hotel, "rating"),
                    _field(hotel, "rating_source"),
                    minimum=0,
                    maximum=5,
                    validation_status=_field(hotel, "rating_validation_status"),
                ) is not None
                for hotel in linked_hotels
            )
            rows.append({
                "name": str(_field(destination, "destination_name", "")).replace("|", r"\|"),
                "attractions": len(destination_attractions),
                "attraction_coords": valid_coordinates,
                "valid_fees": verified_fees,
                "missing_fees": len(destination_attractions) - verified_fees,
                "valid_durations": verified_durations,
                "missing_durations": len(destination_attractions) - verified_durations,
                "valid_ratings": valid_ratings,
                "missing_ratings": len(destination_attractions) - valid_ratings,
                "categorized_attractions": categorized_attractions,
                "missing_categories": len(destination_attractions) - categorized_attractions,
                "pref_eligible": preference_eligible,
                "hotels": len(linked_hotels),
                "hotel_coords": len(valid_hotels),
                "hotel_price": len(priced_hotels),
                "missing_hotel_prices": len(linked_hotels) - len(priced_hotels),
                "accommodation_eligible": len(priced_hotels),
                "hotel_rating": valid_hotel_ratings,
                "missing_hotel_ratings": len(linked_hotels) - valid_hotel_ratings,
                "insufficient_attractions": preference_eligible < MIN_ATTRACTIONS_FOR_SIX_DAYS,
                "insufficient_hotels": not priced_hotels,
            })

        attr_total = len(attractions)
        hotel_total = len(hotels)
        verified_coord_total = sum(row["attraction_coords"] for row in rows)
        preference_total = sum(row["pref_eligible"] for row in rows)
        hotel_coordinate_total = sum(row["hotel_coords"] for row in rows)
        snapshot = _csv_snapshot()
        output = [
            "# Destination Data Quality Audit",
            "",
            "Generated from the local SQLite database and processed catalogs. The audit is read-only.",
            "",
            "## Data lineage",
            "",
            "- Planner/API data source: `travel_planner.db`, populated by `python scripts/populate_db_day2_5.py`.",
            "- CSV-backed discovery catalog: `datasets/processed/destinations.csv`, `datasets/processed/attractions.csv`, and `datasets/processed/hotels.csv`.",
            "- Attraction names and destination assignments originate in `datasets/raw/tourism/india_tourism_dataset.json`.",
            "- Existing hotel names, locations, and raw fields originate in `datasets/raw/hotels/OYO_HOTEL_ROOMS.csv`; its price snapshot date and `Rating` field semantics are not documented.",
            "- Enriched attraction coordinates use exact-name matches from `datasets/osm/northern-zone.gpkg`; the bundle is OpenStreetMap data under ODbL 1.0, snapshot date recorded in `datasets/osm/README`.",
            "",
            "## Overall coverage",
            "",
            f"- Destinations: {len(destinations)}",
            f"- Database attractions: {attr_total}; source-verified coordinates: {verified_coord_total} ({_percent(verified_coord_total, attr_total)} eligible for destination-anchor distance estimates)",
            f"- Attractions with usable text for preference scoring: {preference_total} ({_percent(preference_total, attr_total)})",
            f"- Processed CSV attraction fields with verified values: coordinates {snapshot['verified_coordinates']}; fees {snapshot['verified_fees']}; durations {snapshot['verified_durations']}; ratings {snapshot['verified_ratings']}",
            f"- Hotels: {hotel_total}; destination-linked hotels with verified coordinates: {hotel_coordinate_total} ({_percent(hotel_coordinate_total, hotel_total)})",
            f"- Duplicate attraction records (same destination and normalized name): {duplicate_attractions}",
            f"- Duplicate hotel records (same normalized name and address): {duplicate_hotels}",
            f"- Processed CSV attraction rows: {snapshot['rows']}; verified entry fees {snapshot['verified_fees']}; verified durations {snapshot['verified_durations']}; verified ratings {snapshot['verified_ratings']}",
            "",
            "Numeric values tagged as estimates, undated hotel prices, values without field-level provenance, invalid coordinates, and ratings outside 0–5 are not counted as verified. An attraction is preference-scoreable when its name or sourced category text exists; this does not mean it matches every requested interest. Fewer than six attraction records is flagged as insufficient for a six-day plan with one unique place per day.",
            "",
            "## Per-destination results",
            "",
            "| Destination | Attractions | Verified coords | Missing/unverified coords | Verified categories | Missing categories | Verified fees | Missing/unverified fees | Verified durations | Missing/unverified durations | Verified ratings | Missing/unverified ratings | Preference eligible | Linked hotels | Hotel coords | Usable nightly prices | Accommodation-eligible hotels | <6 attractions | No suitable hotel |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|",
        ]
        for row in rows:
            output.append(
                f"| {row['name']} | {row['attractions']} | {row['attraction_coords']} "
                f"| {row['attractions'] - row['attraction_coords']} | {row['categorized_attractions']} "
                f"| {row['missing_categories']} | {row['valid_fees']} | {row['missing_fees']} "
                f"| {row['valid_durations']} | {row['missing_durations']} "
                f"| {row['valid_ratings']} | {row['missing_ratings']} "
                f"| {row['pref_eligible']} | {row['hotels']} | {row['hotel_coords']} "
                f"| {row['hotel_price']} | {row['accommodation_eligible']} "
                f"| {'yes' if row['insufficient_attractions'] else 'no'} "
                f"| {'yes' if row['insufficient_hotels'] else 'no'} |"
            )
        output.extend([
            "",
            "## Interpretation",
            "",
            "- Attraction `Verified coords` requires in-range India coordinates, a resolved/verified status, a non-estimate source, and a location within 300 km of the destination anchor.",
            "- Hotel selection requires a reliable destination ID or exact normalized city/region address match, verified local coordinates, and a positive nightly price.",
            "- Missing/unverified attraction fees, durations, ratings, and hotel prices remain unavailable; the planner does not infer free entry, default visit length, current nightly prices, or ratings.",
            "- Transportation is a straight-line estimate only when both endpoints are verified. It is not road routing or a live fare.",
            "",
        ])
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(output), encoding="utf-8")
        return REPORT_PATH
    finally:
        db.close()


if __name__ == "__main__":
    report = generate_report()
    print(f"Data-quality report written to {report}")
