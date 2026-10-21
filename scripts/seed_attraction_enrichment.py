"""Legacy entry point retained without applying unsourced attraction values."""

import csv
from pathlib import Path

from app.data.quality import address_matches_destination


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def seed_attraction_data() -> None:
    print(
        "No attraction enrichment was applied. Add only source-backed values "
        "with field-level provenance to the processed catalog."
    )


def check_hotels_for_destination(destination_name: str) -> list[dict]:
    path = PROJECT_ROOT / "datasets" / "processed" / "hotels.csv"
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    matches = [
        row
        for row in rows
        if address_matches_destination(row.get("address"), destination_name)
    ]
    print(f"\nHotels matching '{destination_name}' as an exact location: {len(matches)}")
    for hotel in matches[:3]:
        print(
            f"  {hotel['hotel_id']} | {hotel['name']} | "
            f"price={hotel.get('price_per_night') or 'unavailable'} | "
            f"coordinates={hotel.get('latitude') or 'unavailable'}"
        )
    return matches


if __name__ == "__main__":
    seed_attraction_data()
    for destination in ("Jaipur", "Agra", "Varanasi"):
        check_hotels_for_destination(destination)
