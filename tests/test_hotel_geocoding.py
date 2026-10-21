import pytest
import csv
from pathlib import Path
import sqlite3
from scripts.migrate_validated_hotel_coordinates import migrate_csv, migrate_db

BASE_DIR = Path(".").resolve()
STAGING_CSV = BASE_DIR / "datasets" / "processed" / "hotel_geocoding_results_full.csv"

def test_entity_matching_classifications():
    if not STAGING_CSV.exists():
        pytest.skip("Staging CSV not found.")
    
    with open(STAGING_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cls = row['final_classification']
            assert cls in ['resolved', 'ambiguous', 'rejected', 'not_found', 'invalid'], f"Unknown classification: {cls}"
            if cls == 'resolved':
                # Should have coords
                assert row.get('latitude') and row.get('longitude')
            else:
                pass


def test_null_preservation():
    if not STAGING_CSV.exists():
        pytest.skip()
        
    with open(STAGING_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['final_classification'] != 'resolved':
                assert not row.get('latitude')
                assert not row.get('longitude')

def test_migration_is_idempotent_and_updates_only_its_database(tmp_path):
    processed_csv = tmp_path / "hotels.csv"
    staging_csv = tmp_path / "staging.csv"
    db_path = tmp_path / "test.db"
    processed_csv.write_text(
        "hotel_id,name,latitude,longitude\n1,Example Hotel,,\n",
        encoding="utf-8",
    )
    staging_csv.write_text(
        "hotel_id,final_classification,latitude,longitude,provenance_query,"
        "provenance_matched_entity,provenance_matching_evidence,provenance_source\n"
        "1,resolved,26.9,75.8,query,Example Hotel,exact name,OSM\n",
        encoding="utf-8",
    )

    assert migrate_csv(processed_csv, staging_csv)
    with processed_csv.open("r", encoding="utf-8", newline="") as source:
        count_after_first = sum(1 for _ in csv.DictReader(source))
    assert migrate_csv(processed_csv, staging_csv)
    with processed_csv.open("r", encoding="utf-8", newline="") as source:
        count_after_second = sum(1 for _ in csv.DictReader(source))
    assert count_after_first == count_after_second == 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE hotels (hotel_id INTEGER PRIMARY KEY, latitude REAL, longitude REAL)"
    )
    cur.execute("INSERT INTO hotels (hotel_id) VALUES (1)")
    conn.commit()
    conn.close()

    migrate_db(processed_csv, db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT latitude, longitude FROM hotels WHERE hotel_id = 1")
    assert cur.fetchone() == (26.9, 75.8)
    cur.execute("SELECT count(*) FROM hotels WHERE provenance_query IS NOT NULL AND provenance_query != ''")
    migrated_count = cur.fetchone()[0]
    conn.close()
    assert migrated_count == 1
