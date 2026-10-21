import csv

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.data import database as database_module
from app.data.models import (
    Attraction,
    Base,
    Destination,
    Hotel,
    Itinerary,
    UserRequest,
)
from app.data.quality import address_matches_destination, verified_measure
import scripts.enrich_processed_datasets as enrichment
from scripts.enrich_processed_datasets import _unique_osm_match
from scripts.populate_db_day2_5 import populate_db_idempotent


def test_exact_osm_match_rejects_ambiguous_and_distant_candidates():
    destination = {"latitude": 26.9, "longitude": 75.8}
    candidate = {
        "osm_id": "1",
        "layer": "gis_osm_pois_free",
        "feature_class": "castle",
        "latitude": 26.91,
        "longitude": 75.81,
        "name": "Amer Fort",
        "geometry_method": "point",
    }
    match, status = _unique_osm_match([candidate], destination, "Jaipur")
    assert match is not None
    assert match["osm_id"] == candidate["osm_id"]
    assert status == "exact_name_unique_within_100km"

    duplicate = {**candidate, "osm_id": "2", "latitude": 26.92}
    match, status = _unique_osm_match([candidate, duplicate], destination, "Jaipur")
    assert match is None
    assert status == "ambiguous_exact_name_candidates:2"

    distant = {**candidate, "latitude": 28.6, "longitude": 77.2}
    match, status = _unique_osm_match([distant], destination, "Jaipur")
    assert match is None
    assert status.startswith("no_exact_osm_match")


def test_city_match_requires_suffix_location_not_incidental_text():
    assert address_matches_destination(
        "Alappuzha, Kerala",
        "Kerala Backwaters (Alappuzha & Kumarakom)",
    )
    assert not address_matches_destination(
        "Near OYE Amritsar, New Tippasandra, Bangalore",
        "Amritsar",
        "Punjab",
    )
    assert address_matches_destination("Near Amer Fort, Jaipur, Rajasthan", "Jaipur", "Rajasthan")


def test_unverified_and_undated_measurements_are_not_usable():
    assert verified_measure(
        2500,
        "unverified undated OYO price",
        minimum=0.01,
        validation_status="unavailable_source_snapshot_date_not_provided",
    ) is None
    assert verified_measure(
        4.5,
        "official property page",
        minimum=0,
        maximum=5,
        validation_status="verified",
    ) == 4.5
    assert verified_measure(
        4.5,
        "official property page",
        minimum=0,
        maximum=5,
        validation_status="unresolved",
    ) is None


def test_enrichment_writes_unverified_hotel_values_as_missing(tmp_path, monkeypatch):
    destinations_path = tmp_path / "destinations.csv"
    attractions_path = tmp_path / "attractions.csv"
    hotels_path = tmp_path / "hotels.csv"
    tourism_path = tmp_path / "tourism.json"
    osm_readme = tmp_path / "osm-readme"
    provenance_path = tmp_path / "provenance.csv"
    pd.DataFrame([{
        "destination_id": 1,
        "destination_name": "Jaipur",
        "state": "Rajasthan",
        "country": "India",
        "latitude": 26.9,
        "longitude": 75.8,
    }]).to_csv(destinations_path, index=False)
    pd.DataFrame([{
        "attraction_id": 20,
        "name": "Amer Fort",
        "destination_id": 1,
        "latitude": "",
        "longitude": "",
        "estimated_cost": "",
        "estimated_visit_duration_min": "",
    }]).to_csv(attractions_path, index=False)
    pd.DataFrame([{
        "hotel_id": 4,
        "name": "Example Jaipur Hotel",
        "destination_id": "",
        "latitude": "",
        "longitude": "",
        "price_per_night": 2800,
        "rating": 4.2,
        "currency": "INR",
        "address": "Jaipur, Rajasthan",
        "source": "OYO_HOTEL_ROOMS.csv",
    }]).to_csv(hotels_path, index=False)
    tourism_path.write_text(
        '[{"id": "1", "destination_name": "Jaipur", '
        '"primary_attractions": ["Amer Fort"]}]',
        encoding="utf-8",
    )
    osm_readme.write_text("OpenStreetMap data as of 2024-05-01T00:00:00Z", encoding="utf-8")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        db.add(Destination(
            destination_id=1,
            destination_name="Jaipur",
            state="Rajasthan",
            latitude=26.9,
            longitude=75.8,
        ))
        db.commit()

    monkeypatch.setattr(database_module, "SessionLocal", session_factory)
    monkeypatch.setattr(enrichment, "_existing_db_ids", lambda: {})
    monkeypatch.setattr(enrichment, "_osm_candidates", lambda: {})
    for name, value in (
        ("DESTINATIONS_CSV", destinations_path),
        ("ATTRACTIONS_CSV", attractions_path),
        ("HOTELS_CSV", hotels_path),
        ("TOURISM_JSON", tourism_path),
        ("OSM_README", osm_readme),
        ("PROVENANCE_CSV", provenance_path),
    ):
        monkeypatch.setattr(enrichment, name, value)

    result = enrichment.prepare_processed_datasets(apply=True)
    with hotels_path.open(encoding="utf-8", newline="") as source:
        imported_hotel = next(csv.DictReader(source))
    with attractions_path.open(encoding="utf-8", newline="") as source:
        first_attraction_id = next(csv.DictReader(source))["attraction_id"]
    second_result = enrichment.prepare_processed_datasets(apply=True)
    with hotels_path.open(encoding="utf-8", newline="") as source:
        rerun_hotel = next(csv.DictReader(source))
    with attractions_path.open(encoding="utf-8", newline="") as source:
        rerun_attraction_id = next(csv.DictReader(source))["attraction_id"]
    assert result["hotel_prices_cleared"] == 1
    assert result["hotel_ratings_cleared"] == 1
    assert imported_hotel["price_per_night"] == ""
    assert imported_hotel["rating"] == ""
    assert imported_hotel["price_validation_status"] == "unavailable_source_snapshot_date_not_provided"
    assert imported_hotel["rating_validation_status"] == "unavailable_source_field_semantics_not_verified"
    assert second_result["hotel_prices_cleared"] == 0
    assert rerun_hotel["price_per_night"] == ""
    assert rerun_hotel["rating"] == ""
    assert rerun_attraction_id == first_attraction_id
    engine.dispose()


def _write_import_csvs(tmp_path):
    destinations = pd.DataFrame([{
        "destination_id": 1,
        "destination_name": "Jaipur",
        "state": "Rajasthan",
        "country": "India",
        "latitude": 26.9124,
        "longitude": 75.7873,
        "source": "raw tourism source",
        "source_record_id": "3",
    }])
    attractions = pd.DataFrame([{
        "attraction_id": 44,
        "name": "City Palace",
        "normalized_name": "city palace",
        "destination_id": 1,
        "category": "history",
        "subcategory": "castle",
        "latitude": "",
        "longitude": "",
        "rating": "",
        "rating_source": "",
        "rating_validation_status": "unavailable_no_authoritative_rating_source",
        "estimated_cost": "",
        "cost_source": "",
        "cost_validation_status": "unavailable_no_authoritative_entry_fee_source",
        "estimated_visit_duration_min": "",
        "duration_source": "",
        "duration_validation_status": "unavailable_no_authoritative_duration_source",
        "currency": "INR",
        "source": "india_tourism_dataset.json",
        "source_record_id": "3",
        "source_url": "",
        "coordinate_source": "",
        "coordinate_status": "unresolved",
        "data_quality_status": "missing_unverified_values",
    }])
    hotels = pd.DataFrame([{
        "hotel_id": 8,
        "name": "Sample Jaipur Hotel",
        "normalized_name": "sample jaipur hotel",
        "destination_id": "",
        "latitude": "",
        "longitude": "",
        "price_per_night": "",
        "price_source": "unverified undated OYO source",
        "price_source_url": "",
        "price_validation_status": "unavailable_source_snapshot_date_not_provided",
        "currency": "INR",
        "rating": "",
        "rating_source": "unverified ambiguous field",
        "rating_validation_status": "unavailable_source_field_semantics_not_verified",
        "address": "Jaipur, Rajasthan",
        "source": "OYO_HOTEL_ROOMS.csv",
        "source_record_id": "8",
        "source_url": "",
        "provenance_source": "",
        "data_quality_status": "coordinates_unavailable;price_unverified;rating_unverified",
        "amenities": "{}",
    }])
    files = []
    for name, frame in (
        ("destinations.csv", destinations),
        ("attractions.csv", attractions),
        ("hotels.csv", hotels),
    ):
        path = tmp_path / name
        frame.to_csv(path, index=False)
        files.append(path)
    return files


def test_idempotent_import_preserves_nulls_ids_users_and_saved_trips(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        destination = Destination(
            destination_id=1,
            destination_name="Jaipur",
            state="Rajasthan",
            country="India",
        )
        db.add(destination)
        db.flush()
        db.add_all([
            Attraction(
                attraction_id=44,
                name="City Palace",
                normalized_name="city palace",
                destination_id=destination.destination_id,
                latitude=26.92,
                longitude=75.82,
                estimated_cost=100,
                cost_source="estimated",
                is_active=True,
            ),
            Attraction(
                attraction_id=45,
                name="Superseded duplicate",
                normalized_name="superseded duplicate",
                destination_id=destination.destination_id,
                is_active=True,
            ),
            Hotel(
                hotel_id=8,
                name="Sample Jaipur Hotel",
                normalized_name="sample jaipur hotel",
                destination_id=destination.destination_id,
                address="Jaipur, Rajasthan",
                price_per_night=3000,
                price_source="old unverified rate",
                rating=4.5,
                rating_source="old unverified rating",
            ),
        ])
        db.add(UserRequest(
            request_id=9,
            destination="Jaipur",
            duration=2,
            travelers=1,
            budget=10000,
            currency="INR",
            interests=["history"],
        ))
        db.flush()
        db.add(Itinerary(
            itinerary_id=10,
            request_id=9,
            day_number=1,
            attraction_id=44,
            hotel_id=8,
            sequence_order=1,
            status="saved",
        ))
        db.commit()

    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE app_users (user_id INTEGER PRIMARY KEY, email TEXT NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO app_users (user_id, email) VALUES (1, 'existing@example.test')"
        ))

    destination_path, attraction_path, hotel_path = _write_import_csvs(tmp_path)
    import_args = {
        "destinations_path": destination_path,
        "attractions_path": attraction_path,
        "hotels_path": hotel_path,
        "session_factory": session_factory,
        "db_engine": engine,
    }
    first = populate_db_idempotent(**import_args)
    second = populate_db_idempotent(**import_args)
    assert first["attractions_activated"] == second["attractions_activated"] == 1
    assert first["hotels_upserted"] == second["hotels_upserted"] == 1

    with session_factory() as db:
        imported_attraction = db.get(Attraction, 44)
        superseded = db.get(Attraction, 45)
        imported_hotel = db.get(Hotel, 8)
        saved_trip = db.get(Itinerary, 10)
        assert imported_attraction.name == "City Palace"
        assert imported_attraction.is_active is True
        assert imported_attraction.latitude is None
        assert imported_attraction.estimated_cost is None
        assert imported_attraction.estimated_visit_duration_min is None
        assert superseded is not None
        assert superseded.is_active is False
        assert imported_hotel.price_per_night is None
        assert imported_hotel.rating is None
        assert imported_hotel.destination_id == 1
        assert saved_trip is not None
        assert saved_trip.attraction_id == 44
        assert saved_trip.hotel_id == 8
        assert db.query(Attraction).count() == 2
        assert db.query(Hotel).count() == 1
        assert db.query(UserRequest).count() == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM app_users")).scalar_one() == 1
    engine.dispose()
