#!/usr/bin/env python3
import warnings
import urllib3
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
import csv
import json
import time
import sys
import hashlib
import os
import datetime
import random
from pathlib import Path
from difflib import SequenceMatcher
import requests

sys.path.append(str(Path(__file__).parent.parent))
from app.data.hotel_query_normalizer import HotelQueryNormalizer

DATA_PATH = Path("datasets/processed/hotels.csv")
STAGING_CSV = Path("datasets/processed/hotel_geocoding_results_full.csv")
CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
USER_AGENT = "TravelPlanner/2.9.3 (contact: admin_dev@travelplanner.example)"
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

def perform_nominatim_request(params: dict) -> tuple:
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
            time.sleep(RATE_LIMIT_SECONDS)
            if resp.status_code == 200:
                return resp.json(), resp.status_code, attempt
            elif resp.status_code in [403, 429]:
                print(f"Rate limited (status {resp.status_code}), waiting...", flush=True)
                time.sleep(RATE_LIMIT_SECONDS * (10 ** (attempt + 1)))
            else:
                time.sleep(RATE_LIMIT_SECONDS * 2)
                if attempt == max_retries - 1:
                    return [], resp.status_code, attempt
        except Exception as e:
            print(f"Request failed: {e}")
            time.sleep(RATE_LIMIT_SECONDS * (2 ** attempt))
            if attempt == max_retries - 1:
                return [], 0, attempt
    return [], 0, max_retries

def nominatim_search(query: str, limit: int = 5):
    cache_file = cache_path(query)
    if cache_file.exists():
        STATS["cached_reused"] += 1
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f), "cache_hit", 200, 0
            
    STATS["queried"] += 1
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
    }
    
    data, http_status, retry_count = perform_nominatim_request(params)
    if data:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    return data, "cache_miss", http_status, retry_count

def progressive_search(source_name: str, source_city: str, source_address: str, normalizer: HotelQueryNormalizer):
    normalized_name, _ = normalizer.normalize(source_name)
    queries = normalizer.generate_queries(normalized_name, source_city, source_address)
    
    for i, q in enumerate(queries):
        candidates, cache_status, http_status, retry_count = nominatim_search(q)
        if candidates:
            return candidates, q, f"Query {i+1}", normalized_name, cache_status, http_status, retry_count
            
    last_q = queries[-1] if queries else ""
    return [], last_q, f"Query {len(queries)}" if queries else "", normalized_name, "N/A", 0, 0

import re
def clean_hotel_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r'[^\w\s]', '', n)
    generics = ['hotel', 'resort', 'inn', 'palace', 'pvt', 'ltd', 'private', 'limited', 'spa']
    for g in generics:
        n = re.sub(rf'\b{g}\b', '', n)
    return ' '.join(sorted(n.split()))

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

def extract_candidate_name(display_name: str) -> str:
    if not display_name:
        return ""
    return display_name.split(',')[0].strip()

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
    
    out_keys = list(fieldnames) + [
        "original_hotel_name", "normalized_search_name", "query_variant", "query_used", "provenance_query",
        "http_status", "cache_status", "retry_count", "candidate_count",
        "matched_name", "matched_address", "matched_latitude", "matched_longitude",
        "name_similarity", "city_match", "address_match", "geographic_consistency", 
        "osm_type_category", "classification", "classification_reason", "timestamp", "error_status", "final_classification",
        "latitude", "longitude"
    ]
    
    needs_coords = []
    for r in rows:
        if not (r.get('latitude') and str(r.get('latitude')).strip()):
            needs_coords.append(r)
    
    print(f"Total Hotels: {STATS['total_hotels']}")
    print(f"Running on all remaining: {len(needs_coords)} hotels")

    f_staging = open(STAGING_CSV, 'w', newline='', encoding='utf-8')
    writer = csv.DictWriter(f_staging, fieldnames=out_keys)
    writer.writeheader()

    normalizer = HotelQueryNormalizer()
    
    for count, row in enumerate(needs_coords):
        source_name = row.get('name', '').strip()
        source_address = row.get('address', '').strip()
        source_city = extract_city(source_address) or extract_city(row.get('source', ''))
        
        candidates, final_query, query_variant, norm_name, cache_status, http_status, retry_count = progressive_search(
            source_name, source_city, source_address, normalizer
        )
        
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        out_row = {k: row.get(k, '') for k in fieldnames}
        
        out_row.update({
            "original_hotel_name": source_name,
            "normalized_search_name": norm_name,
            "query_variant": query_variant,
            "query_used": final_query,
            "provenance_query": final_query,
            "http_status": http_status,
            "cache_status": cache_status,
            "retry_count": retry_count,
            "candidate_count": len(candidates),
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
            "classification_reason": "No candidates found",
            "final_classification": "not_found",
            "timestamp": timestamp_str,
            "error_status": "OK",
            "latitude": "",
            "longitude": ""
        })

        if candidates:
            scored = []
            for cand in candidates:
                cand_name = extract_candidate_name(cand.get('display_name', ''))
                cand_city = candidate_city(cand)
                cand_type = cand.get('type', '')
                sim = name_similarity(source_name, cand_name)
                city_ok = (source_city.lower() == cand_city.lower()) if source_city and cand_city else False
                addr_ok = address_match(source_address, cand_name)
                type_ok = map_osm_category(cand_type) == "yes"
                
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
            
            sim = top["name_similarity"]
            city_ok = top["city_match"]
            type_ok = top["type_match"]
            addr_ok = top["address_match"]
            
            classification_reason = ""
            if is_generic_name(source_name):
                if sim >= 0.90 and city_ok and type_ok and addr_ok:
                    classification = "resolved"
                    classification_reason = "Generic name met strict thresholds"
                else:
                    classification = "ambiguous" if city_ok else "rejected"
                    classification_reason = "Generic name failed strict thresholds"
            else:
                if sim >= 0.85 and city_ok and type_ok:
                    classification = "resolved"
                    classification_reason = "High sim, city match, type match"
                elif sim >= 0.85 and city_ok and addr_ok:
                    classification = "resolved"
                    classification_reason = "High sim, city match, address match"
                elif sim >= 0.85 and not city_ok:
                    classification = "rejected" 
                    classification_reason = "High sim but city mismatch"
                elif len(scored) > 1 and sum(1 for s in scored if s["city_match"] and s["name_similarity"] > 0.6) > 1:
                    classification = "ambiguous"
                    classification_reason = "Multiple plausible candidates in city"
                elif sim < 0.6:
                    classification = "invalid"
                    classification_reason = "Name similarity too low"
                else:
                    classification = "rejected"
                    classification_reason = "Failed matching criteria"
            
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
                "classification_reason": classification_reason,
                "final_classification": classification,
                "latitude": cand.get('lat', '') if classification == 'resolved' else '',
                "longitude": cand.get('lon', '') if classification == 'resolved' else '',
            })

        STATS[out_row["classification"]] += 1
        STATS["processed"] += 1
        writer.writerow(out_row)

    f_staging.close()
    
    print("=== LIVE GEOCODING RUN SUMMARY ===")
    print(f"Total hotels API Queried: {STATS['queried']}")
    print(f"Processed this / total: {STATS['processed']}")
    print(f"Resolved: {STATS['resolved']}")
    print(f"Ambiguous: {STATS['ambiguous']}")
    print(f"Rejected: {STATS['rejected']}")
    print(f"Not Found: {STATS['not_found']}")
    print(f"Invalid: {STATS['invalid']}")

if __name__ == '__main__':
    main()
