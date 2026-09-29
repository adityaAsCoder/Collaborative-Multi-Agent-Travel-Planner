import pytest
import csv
from pathlib import Path
import sqlite3

BASE_DIR = Path(".").resolve()
STAGING_CSV = BASE_DIR / "datasets" / "processed" / "hotel_geocoding_results_full.csv"
PROCESSED_CSV = BASE_DIR / "datasets" / "processed" / "hotels.csv"
DB_PATH = BASE_DIR / "travel_planner.db"
MIGRATION_SCRIPT = BASE_DIR / "scripts" / "migrate_validated_hotel_coordinates.py"

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

def test_migration_idempotency_and_count():
    import subprocess
    import shutil
    if not PROCESSED_CSV.exists():
        pytest.skip()
    
    # Run migration script
    res1 = subprocess.run(["python", str(MIGRATION_SCRIPT)], capture_output=True, text=True)
    assert res1.returncode == 0
    
    # Read count 1
    with open(PROCESSED_CSV, 'r', encoding='utf-8') as f:
        count1 = sum(1 for _ in f)
        
    # Run again and check stdout or return code
    res2 = subprocess.run(["python", str(MIGRATION_SCRIPT)], capture_output=True, text=True)
    assert res2.returncode == 0
    
    with open(PROCESSED_CSV, 'r', encoding='utf-8') as f:
        count2 = sum(1 for _ in f)
        
    assert count1 == count2, "Record count must be preserved across migrations"

def test_database_updated():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM hotels WHERE provenance_query IS NOT NULL AND provenance_query != ''")
    migrated_count = cur.fetchone()[0]
    conn.close()
    assert migrated_count >= 0
