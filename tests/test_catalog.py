from pathlib import Path

import pandas as pd

from app.data.catalog import (
    build_itinerary,
    destination_attractions,
    search_destinations,
)


ROOT = Path(__file__).resolve().parents[1]


def test_search_matches_destination_and_region():
    destinations = pd.read_csv(ROOT / "datasets/processed/destinations.csv").fillna("")
    result = search_destinations(destinations, "Rajasthan")
    assert not result.empty
    assert "Jaipur" in result["destination_name"].tolist()


def test_interest_ranking_uses_attraction_text():
    attractions = pd.DataFrame(
        [
            {"destination_id": 1, "name": "History Fort", "category": "History", "subcategory": "", "description": "", "rating": 3, "popularity": 0},
            {"destination_id": 1, "name": "Quiet Park", "category": "Nature", "subcategory": "", "description": "", "rating": 5, "popularity": 0},
        ]
    )
    ranked = destination_attractions(attractions, 1, ["history"])
    assert ranked.iloc[0]["name"] == "History Fort"


def test_itinerary_has_requested_days_and_no_duplicates():
    attractions = pd.DataFrame([{"name": f"Place {i}"} for i in range(6)])
    itinerary = build_itinerary(attractions, duration=3, max_per_day=2)
    assert len(itinerary) == 3
    names = [item["name"] for day in itinerary for item in day["attractions"]]
    assert len(names) == len(set(names)) == 6
