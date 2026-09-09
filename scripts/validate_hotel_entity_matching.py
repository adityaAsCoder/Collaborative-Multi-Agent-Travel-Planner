#!/usr/bin/env python3
"""Hotel Entity Matching Validation (Day 2.8B)

- Reads the processed hotels CSV (missing coordinates).
- Selects a deterministic sample of 30 hotels.
- Queries Nominatim (limit 5) for each hotel.
- Scores each candidate using multiple signals.
- Classifies as resolved / ambiguous / rejected / not_found.
- Writes a staging CSV with detailed fields.
- Generates a markdown validation report.
"""
import csv
import json
import time
import hashlib
import os
from pathlib import Path
from difflib import SequenceMatcher
import requests
import random

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_PATH = Path(__file__).resolve().parents[1] / "datasets" / "processed" / "hotels.csv"
RESULT_CSV = Path(__file__).resolve().parents[1] / "datasets" / "processed" / "hotel_geocoding_results.csv"
REPORT_MD = Path(__file__).resolve().parents[1] / "reports" / "data_inspection" / "hotel_entity_matching_validation.md"
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
USER_AGENT = "TravelPlanner/2.8B (contact: dev@travelplanner.example)"
RATE_LIMIT_SECONDS = 1.0

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def cache_path(query: str) -> Path:
    h = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"nominatim_{h}.json"

def nominatim_search(query: str, limit: int = 5):
    cache_file = cache_path(query)
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
    }
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=30)
    time.sleep(RATE_LIMIT_SECONDS)  # rate limiting
    if resp.status_code != 200:
        raise RuntimeError(f"Nominatim request failed: {resp.status_code}")
    data = resp.json()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    # logging (append short line)
    with open(Path(__file__).resolve().parents[1] / "geocode_log.txt", "a", encoding="utf-8") as logf:
        logf.write(f"{time.time():.0f}\t{query}\t{resp.status_code}\t{len(data)}\n")
    return data

def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_city(address_field: str) -> str:
    # address field often looks like "Near X, City" or "City, State"
    if not address_field:
        return ""
    parts = [p.strip() for p in address_field.split(',') if p.strip()]
    # heuristics: last part is likely city/state, but we try to find known city names later.
    return parts[-1] if parts else ""

def candidate_city(candidate: dict) -> str:
    addr = candidate.get('address', {})
    for key in ('city', 'town', 'village', 'municipality'):
        if key in addr:
            return addr[key]
    # fallback to county or state
    return addr.get('state', '')

def address_match(source_addr: str, candidate_display: str) -> bool:
    if not source_addr:
        return False
    src = source_addr.lower()
    cand = candidate_display.lower()
    return src in cand or cand in src

# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def main(sample_size: int = 30, random_seed: int = 42):
    # Load hotels CSV
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if not r.get('latitude') and not r.get('longitude')]
    random.seed(random_seed)
    sample = random.sample(rows, min(sample_size, len(rows)))

    fieldnames = [
        "hotel_id",
        "source_name",
        "source_city",
        "source_address",
        "candidate_name",
        "candidate_city",
        "candidate_address",
        "latitude",
        "longitude",
        "name_similarity",
        "city_match",
        "address_match",
        "final_classification",
        "confidence",
        "reason",
    ]
    os.makedirs(RESULT_CSV.parent, exist_ok=True)
    with open(RESULT_CSV, "w", newline="", encoding="utf-8") as outcsv:
        writer = csv.DictWriter(outcsv, fieldnames=fieldnames)
        writer.writeheader()
        for row in sample:
            source_name = row.get('name', '').strip()
            source_address = row.get('address', '').strip()
            source_city = extract_city(source_address) or extract_city(row.get('source', ''))
            query = f"{source_name} {source_city}" if source_city else source_name
            candidates = nominatim_search(query, limit=5)
            if not candidates:
                classification = "not_found"
                writer.writerow({
                    "hotel_id": row.get('hotel_id'),
                    "source_name": source_name,
                    "source_city": source_city,
                    "source_address": source_address,
                    "candidate_name": "",
                    "candidate_city": "",
                    "candidate_address": "",
                    "latitude": "",
                    "longitude": "",
                    "name_similarity": "",
                    "city_match": "",
                    "address_match": "",
                    "final_classification": classification,
                    "confidence": "0",
                    "reason": "no candidates returned",
                })
                continue
            # Score each candidate
            scored = []
            for cand in candidates:
                cand_name = cand.get('display_name', '')
                cand_city = candidate_city(cand)
                sim = name_similarity(source_name, cand_name)
                city_ok = (source_city.lower() == cand_city.lower()) if source_city and cand_city else False
                addr_ok = address_match(source_address, cand_name)
                confidence = (sim * 0.6) + (0.2 if city_ok else 0) + (0.2 if addr_ok else 0)
                scored.append({
                    "candidate": cand,
                    "name_similarity": sim,
                    "city_match": city_ok,
                    "address_match": addr_ok,
                    "confidence": confidence,
                })
            # Sort by confidence descending
            scored.sort(key=lambda x: x["confidence"], reverse=True)
            top = scored[0]
            # Determine classification
            if top["name_similarity"] >= 0.85 and top["city_match"] and top["address_match"]:
                classification = "resolved"
                reason = "name + city + address matched"
            elif top["name_similarity"] >= 0.85 and not top["city_match"]:
                classification = "rejected"
                reason = "high name similarity but city mismatch (potential false positive)"
            elif len(scored) > 1 and any(s["city_match"] for s in scored[:3]):
                classification = "ambiguous"
                reason = "multiple plausible candidates with city match"
            else:
                classification = "rejected"
                reason = "insufficient similarity or missing city match"
            cand = top["candidate"]
            writer.writerow({
                "hotel_id": row.get('hotel_id'),
                "source_name": source_name,
                "source_city": source_city,
                "source_address": source_address,
                "candidate_name": cand.get('display_name', ''),
                "candidate_city": candidate_city(cand),
                "candidate_address": cand.get('type', ''),
                "latitude": cand.get('lat', ''),
                "longitude": cand.get('lon', ''),
                "name_similarity": f"{top['name_similarity']:.3f}",
                "city_match": str(top['city_match']),
                "address_match": str(top['address_match']),
                "final_classification": classification,
                "confidence": f"{top['confidence']:.3f}",
                "reason": reason,
            })

    # -----------------------------------------------------------------------
    # Generate markdown report summary
    # -----------------------------------------------------------------------
    summary_counts = {"resolved": 0, "ambiguous": 0, "rejected": 0, "not_found": 0}
    rows_report = []
    with open(RESULT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cls = r["final_classification"]
            summary_counts[cls] = summary_counts.get(cls, 0) + 1
            rows_report.append(r)
    os.makedirs(REPORT_MD.parent, exist_ok=True)
    with open(REPORT_MD, "w", encoding="utf-8") as md:
        md.write("# Hotel Entity Matching Validation (Day 2.8B)\n\n")
        md.write(f"Sample size: {len(rows_report)} hotels (selected from missing‑coordinate set)\n\n")
        md.write("## Classification Summary\n\n")
        for k, v in summary_counts.items():
            md.write(f"- {k}: {v}\n")
        md.write("\n## Detailed Results (first 30 rows)\n\n")
        md.write("| hotel_id | source_name | source_city | candidate_name | candidate_city | classification | confidence | reason |\n")
        md.write("|---|---|---|---|---|---|---|---|\n")
        for r in rows_report[:30]:
            md.write(f"| {r['hotel_id']} | {r['source_name']} | {r['source_city']} | {r['candidate_name']} | {r['candidate_city']} | {r['final_classification']} | {r['confidence']} | {r['reason']} |\n")
    print(f"Validation complete. CSV: {RESULT_CSV}\nReport: {REPORT_MD}")

if __name__ == "__main__":
    main()
