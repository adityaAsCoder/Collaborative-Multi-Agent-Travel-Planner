#!/usr/bin/env python3
"""Report missing latitude/longitude in hotels dataset.
Generates a markdown report at reports/missing_hotel_coordinates.md
with total count and a sample of affected rows.
"""
import csv
import os
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "datasets" / "processed" / "hotels.csv"
REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "missing_hotel_coordinates.md"

missing_rows = []
with open(DATA_PATH, newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        lat = row.get("latitude", "").strip()
        lon = row.get("longitude", "").strip()
        if not lat or not lon:
            missing_rows.append(row)

total = sum(1 for _ in open(DATA_PATH, "r", encoding="utf-8")) - 1  # exclude header
missing_count = len(missing_rows)

os.makedirs(REPORT_PATH.parent, exist_ok=True)
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("# Missing Hotel Coordinates Report\n\n")
    f.write(f"Total hotel records: {total}\n\n")
    f.write(f"Rows with missing latitude or longitude: {missing_count}\n\n")
    f.write("## Sample rows (up to 20)\n\n")
    if missing_rows:
        headers = missing_rows[0].keys()
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "---|" * len(headers) + "\n")
        for row in missing_rows[:20]:
            f.write("| " + " | ".join(row[h] if row[h] is not None else "" for h in headers) + " |\n")
    else:
        f.write("No missing coordinates found.\n")

print(f"Report written to {REPORT_PATH}")
