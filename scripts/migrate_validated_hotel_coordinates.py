#!/usr/bin/env python3
import csv
import sqlite3
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(".").resolve()
PROCESSED_CSV = BASE_DIR / "datasets" / "processed" / "hotels.csv"
STAGING_CSV = BASE_DIR / "datasets" / "processed" / "hotel_geocoding_results_full.csv"
DB_PATH = BASE_DIR / "travel_planner.db"

def migrate_csv():
    # backup
    backup_path = PROCESSED_CSV.with_suffix(".csv.bak")
    shutil.copy(PROCESSED_CSV, backup_path)

    # Read original
    original_hotels = []
    with open(PROCESSED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for r in reader:
            original_hotels.append(r)
    
    orig_count = len(original_hotels)

    # Read staging
    staging_updates = {}
    if STAGING_CSV.exists():
        with open(STAGING_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("final_classification") == "resolved" and r.get("latitude") and r.get("longitude"):
                    staging_updates[r["hotel_id"]] = {
                        "latitude": r["latitude"],
                        "longitude": r["longitude"],
                        "provenance_query": r.get("provenance_query", ""),
                        "provenance_matched_entity": r.get("provenance_matched_entity", ""),
                        "provenance_matching_evidence": r.get("provenance_matching_evidence", ""),
                        "provenance_source": r.get("provenance_source", "")
                    }
    
    extra_fields = ["provenance_query", "provenance_matched_entity", "provenance_matching_evidence", "provenance_source"]
    for e in extra_fields:
        if e not in fieldnames:
            fieldnames.append(e)
            
    # Apply updates
    for row in original_hotels:
        hid = row["hotel_id"]
        # Only update if the row lacks latitude/longitude, or if we are overwriting nulls idempotently
        # Wait, if it has coords already, we keep them.
        # Idempotency: if it's already filled, don't break it. 
        # But if staging provides resolution, use it.
        if hid in staging_updates:
            # check if original coords are empty or if we should overwrite
            row["latitude"] = staging_updates[hid]["latitude"]
            row["longitude"] = staging_updates[hid]["longitude"]
            row["provenance_query"] = staging_updates[hid]["provenance_query"]
            row["provenance_matched_entity"] = staging_updates[hid]["provenance_matched_entity"]
            row["provenance_matching_evidence"] = staging_updates[hid]["provenance_matching_evidence"]
            row["provenance_source"] = staging_updates[hid]["provenance_source"]

    # Write back
    with open(PROCESSED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(original_hotels)
    
    print(f"CSV Migration complete. Processed {orig_count} => {len(original_hotels)} rows.")
    return orig_count == len(original_hotels)

def migrate_db():
    # Update SQLite
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # ensure columns exist
    cur.execute("PRAGMA table_info(hotels)")
    cols = [r[1] for r in cur.fetchall()]
    extra_fields = ["provenance_query", "provenance_matched_entity", "provenance_matching_evidence", "provenance_source"]
    for e in extra_fields:
        if e not in cols:
            cur.execute(f"ALTER TABLE hotels ADD COLUMN {e} TEXT")
            
    # read the updated canonical csv
    updates = []
    with open(PROCESSED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("latitude") and r.get("longitude"):
                updates.append((
                    r["latitude"], r["longitude"],
                    r.get("provenance_query", ""), r.get("provenance_matched_entity", ""),
                    r.get("provenance_matching_evidence", ""), r.get("provenance_source", ""),
                    r["hotel_id"]
                ))
    
    cur.executemany("""
        UPDATE hotels 
        SET latitude = ?, longitude = ?, provenance_query = ?, provenance_matched_entity = ?, provenance_matching_evidence = ?, provenance_source = ? 
        WHERE hotel_id = ?
    """, updates)
    
    conn.commit()
    conn.close()
    print("Database Migration complete.")

if __name__ == "__main__":
    if migrate_csv():
        migrate_db()
    else:
        print("CSV Migration failed validation (count mismatch).")
        sys.exit(1)
