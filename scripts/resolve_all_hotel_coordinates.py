#!/usr/bin/env python3
import warnings
import urllib3
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
import csv
import json
import time
import hashlib
import os
import datetime
from pathlib import Path
from difflib import SequenceMatcher
import requests

DATA_PATH = Path("datasets/processed/hotels.csv")
STAGING_CSV = Path("datasets/processed/hotel_geocoding_results_full.csv")
CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
USER_AGENT = "TravelPlanner/2.9.1 (contact: admin_dev@travelplanner.example)"
RATE_LIMIT_SECONDS = 1.0

STATS = {
    "total_hotels": 0,
    "already_geocoded": 0,
    "processed": 0,
    "resolved": 0,
    "ambiguous": 0,
    "rejected": 0,
    "not_found": 0,
    "invalid": 0,
    "queried": 0,
    "cached_reused": 0,
    "live_requests": 0
}

def cache_path(query: str) -> Path:
    h = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"nominatim_{h}.json"

def perform_nominatim_request(params: dict) -> list:
    headers = {"User-Agent": USER_AGENT}
    max_retries = 3
    for attempt in range(max_retries):
        STATS["live_requests"] += 1
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search", 
                params=params, 
                headers=headers, 
                timeout=15
            )
            time.sleep(RATE_LIMIT_SECONDS) # Strict request per second pacing
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in [403, 429]:
                print(f"Rate limited (status {resp.status_code}), waiting...", flush=True)
                time.sleep(RATE_LIMIT_SECONDS * (10 ** (attempt + 1)))
            else:
                time.sleep(RATE_LIMIT_SECONDS * 2)
        except Exception as e:
            print(f"Request failed: {e}")
            time.sleep(RATE_LIMIT_SECONDS * (2 ** attempt))
    return []

def nominatim_search(query: str, limit: int = 5):
    cache_file = cache_path(query)
    if cache_file.exists():
        STATS["cached_reused"] += 1
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
            
    STATS["queried"] += 1
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
    }
    
    data = perform_nominatim_request(params)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data

def progressive_search(source_name: str, source_city: str, source_address: str):
    # Progressive queries:
    # a. hotel name + city
    # b. hotel name + address/location + city
    # c. hotel name + locality + city (extract locality from address if possible)
    
    # Query A
    q_a = f"{source_name} {source_city}".strip()
    candidates = nominatim_search(q_a)
    if candidates:
        return candidates, q_a
        
    # Query B
    if source_address:
        q_b = f"{source_name}, {source_address}, {source_city}".strip()
        candidates = nominatim_search(q_b)
        if candidates:
            return candidates, q_b
            
    # Query C
    # Extract locality as maybe the first part of address
    locality = ""
    if source_address and "," in source_address:
        parts = [p.strip() for p in source_address.split(",")]
        if len(parts) > 1:
            locality = parts[0]
            q_c = f"{source_name} {locality} {source_city}".strip()
            candidates = nominatim_search(q_c)
            if candidates:
                return candidates, q_c
                
    return [], q_a

import re
def clean_hotel_name(name: str) -> str:
    # Remove generic words, punctuation and make lowercase for cleaner similarity check
    n = name.lower()
    n = re.sub(r'[^\w\s]', '', n)
    generics = ['hotel', 'resort', 'inn', 'palace', 'pvt', 'ltd', 'private', 'limited', 'spa']
    for g in generics:
        n = re.sub(rf'\b{g}\b', '', n)
    return ' '.join(sorted(n.split())) # sort words to handle "ABC Hotel" vs "Hotel ABC"

def name_similarity(a: str, b: str) -> float:
    a_clean = clean_hotel_name(a)
    b_clean = clean_hotel_name(b)
    if not a_clean or not b_clean: 
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return SequenceMatcher(None, a_clean, b_clean).ratio()

def extract_city(address_field: str) -> str:
    if not address_field:
        return ""
    parts = [p.strip() for p in address_field.split(',') if p.strip()]
    return parts[-1] if parts else ""

def candidate_city(candidate: dict) -> str:
    addr = candidate.get('address', {})
    for key in ('city', 'town', 'village', 'municipality'):
        if key in addr:
            return addr[key]
    return addr.get('state', '')

def address_match(source_addr: str, candidate_display: str) -> bool:
    if not source_addr:
        return False
    src = source_addr.lower()
    cand = candidate_display.lower()
    return src in cand or cand in src

def map_osm_category(cand_type: str) -> str:
    if cand_type in ['hotel', 'guest_house', 'hostel', 'motel', 'chalet', 'apartment']:
        return "yes"
    return "no"

def is_generic_name(name: str):
    # simple generic check
    generic_words = ["hotel", "motel", "inn", "guesthouse", "hostel"]
    name_clean = name.lower().strip()
    return name_clean in generic_words

def main():
    rows = []
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for r in reader:
            rows.append(r)
            
    STATS["total_hotels"] = len(rows)
    
    # Load previously processed
    processed_hotel_ids = set()
    staged_results = []
    out_keys = list(fieldnames) + [
        "provenance_query", "matched_name", "matched_address", "matched_latitude", "matched_longitude",
        "name_similarity", "city_match", "address_match", "geographic_consistency", 
        "osm_type_category", "classification", "timestamp", "error_status", "final_classification"
    ]
    
    if STAGING_CSV.exists():
        with open(STAGING_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                processed_hotel_ids.add(r["hotel_id"])
                staged_results.append(r)
                if r.get("classification"):
                    cls = r["classification"]
                    if cls in STATS:
                        STATS[cls] += 1
                        STATS["processed"] += 1
    
    needs_coords = []
    for r in rows:
        if r.get('latitude') and str(r.get('latitude')).strip():
            STATS["already_geocoded"] += 1
        elif r['hotel_id'] not in processed_hotel_ids:
            needs_coords.append(r)
    
    print(f"Total Hotels: {STATS['total_hotels']}, Already Geocoded: {STATS['already_geocoded']}")
    print(f"Remaining to process: {len(needs_coords)}")

    # Open CSV in append mode if it exists, else write header
    mode = 'a' if STAGING_CSV.exists() else 'w'
    f_staging = open(STAGING_CSV, mode, newline='', encoding='utf-8')
    writer = csv.DictWriter(f_staging, fieldnames=out_keys)
    if mode == 'w':
        writer.writeheader()

    for count, row in enumerate(needs_coords):
        if (count+1) % 10 == 0:
            print(f"Geocoding progress... {count+1}/{len(needs_coords)}", flush=True)
            f_staging.flush()

        source_name = row.get('name', '').strip()
        source_address = row.get('address', '').strip()
        source_city = extract_city(source_address) or extract_city(row.get('source', ''))
        
        candidates, final_query = progressive_search(source_name, source_city, source_address)
        
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        out_row = {k: row.get(k, '') for k in fieldnames}
        out_row.update({
            "provenance_query": final_query,
            "matched_name": "",
            "matched_address": "",
            "matched_latitude": "",
            "matched_longitude": "",
            "name_similarity": "",
            "city_match": "",
            "address_match": "",
            "geographic_consistency": "",
            "osm_type_category": "",
            "classification": "not_found",
            "final_classification": "not_found",
            "timestamp": timestamp_str,
            "error_status": "OK",
            # for backwards compatibility with earlier script
            "latitude": "",
            "longitude": ""
        })

        if not candidates:
            out_row["classification"] = "not_found"
            out_row["final_classification"] = "not_found"
        else:
            scored = []
            for cand in candidates:
                cand_name = cand.get('display_name', '')
                cand_city = candidate_city(cand)
                cand_type = cand.get('type', '')
                sim = name_similarity(source_name, cand_name)
                city_ok = (source_city.lower() == cand_city.lower()) if source_city and cand_city else False
                addr_ok = address_match(source_address, cand_name)
                type_ok = map_osm_category(cand_type) == "yes"
                
                # geographic consistency placeholder
                geo_ok = True
                
                confidence = (sim * 0.5) + (0.2 if city_ok else 0) + (0.1 if addr_ok else 0) + (0.2 if type_ok else 0)
                
                scored.append({
                    "candidate": cand,
                    "name_similarity": sim,
                    "city_match": city_ok,
                    "address_match": addr_ok,
                    "type_match": type_ok,
                    "geo_match": geo_ok,
                    "confidence": confidence,
                })
            
            scored.sort(key=lambda x: x["confidence"], reverse=True)
            top = scored[0]
            cand = top["candidate"]
            
            # Classification Policy (Day 2.8B)
            sim = top["name_similarity"]
            city_ok = top["city_match"]
            type_ok = top["type_match"]
            addr_ok = top["address_match"]
            
            if is_generic_name(source_name):
                # generic generic need strict rules
                if sim >= 0.90 and city_ok and type_ok and addr_ok:
                    classification = "resolved"
                else:
                    classification = "ambiguous" if city_ok else "rejected"
            else:
                if sim >= 0.85 and city_ok and type_ok:
                    classification = "resolved"
                elif sim >= 0.85 and city_ok and addr_ok:
                    classification = "resolved"
                elif sim >= 0.85 and not city_ok:
                    classification = "rejected" # High name sim but different city must NOT be accepted
                elif len(scored) > 1 and sum(1 for s in scored if s["city_match"] and s["name_similarity"] > 0.6) > 1:
                    classification = "ambiguous"
                elif sim < 0.6:
                    classification = "invalid"
                else:
                    classification = "rejected"
            
            out_row.update({
                "matched_name": cand.get('display_name', ''),
                "matched_address": cand.get('display_name', ''),
                "matched_latitude": cand.get('lat', ''),
                "matched_longitude": cand.get('lon', ''),
                "name_similarity": f"{sim:.3f}",
                "city_match": str(city_ok),
                "address_match": str(addr_ok),
                "geographic_consistency": str(top["geo_match"]),
                "osm_type_category": cand.get('type', ''),
                "classification": classification,
                "final_classification": classification, # for backwards compat
                "latitude": cand.get('lat', '') if classification == 'resolved' else '',
                "longitude": cand.get('lon', '') if classification == 'resolved' else '',
            })

        STATS[out_row["classification"]] += 1
        STATS["processed"] += 1
        writer.writerow(out_row)

    f_staging.close()
    
    # Calculate coverage
    total_geocoded = STATS["already_geocoded"] + STATS["resolved"]
    coverage = (total_geocoded / STATS["total_hotels"]) * 100 if STATS["total_hotels"] > 0 else 0
    
    # Output final summary
    print("=== LIVE GEOCODING RUN SUMMARY ===")
    print(f"Total hotels API Queried: {STATS['queried']}")
    print(f"Cached results reused: {STATS['cached_reused']}")
    print(f"Live network requests made: {STATS['live_requests']}")
    print(f"Total Hotels: {STATS['total_hotels']}")
    print(f"Already Geocoded: {STATS['already_geocoded']}")
    print(f"Processed this / total: {STATS['processed']}")
    print(f"Resolved: {STATS['resolved']}")
    print(f"Ambiguous: {STATS['ambiguous']}")
    print(f"Rejected: {STATS['rejected']}")
    print(f"Not Found: {STATS['not_found']}")
    print(f"Invalid: {STATS['invalid']}")
    print(f"Coordinate Coverage: {coverage:.2f}%")

if __name__ == '__main__':
    main()
