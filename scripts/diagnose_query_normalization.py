#!/usr/bin/env python3
import warnings
import urllib3
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
import csv
import json
import time
import hashlib
from pathlib import Path
import requests
import random
from app.data.hotel_query_normalizer import HotelQueryNormalizer

DATA_PATH = Path("datasets/processed/hotels.csv")
CACHE_DIR = Path(".cache")
USER_AGENT = "TravelPlanner/2.9.3 (contact: validation@travelplanner.example)"

def cache_path(query: str) -> Path:
    h = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"nominatim_{h}.json"

def get_live_response(query: str):
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": 5,
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search", 
            params=params, 
            headers=headers, 
            timeout=(2.0, 3.0)
        )
        time.sleep(1.0)
        return {"status": resp.status_code, "data": resp.json() if resp.status_code==200 else [], "error": None}
    except Exception as e:
        time.sleep(1.0)
        return {"status": 0, "data": [], "error": str(e)}

def extract_city(address_field: str) -> str:
    if not address_field:
        return ""
    parts = [p.strip() for p in address_field.split(',') if p.strip()]
    return parts[-1] if parts else ""

def generate_old_queries(source_name, source_address, source_city):
    q_a = f"{source_name} {source_city}".strip()
    q_b = f"{source_name}, {source_address}, {source_city}".strip()
    
    locality = ""
    if source_address and "," in source_address:
        parts = [p.strip() for p in source_address.split(",")]
        if len(parts) > 1:
            locality = parts[0]
    q_c = f"{source_name} {locality} {source_city}".strip() if locality else ""
    return [q for q in [q_a, q_b, q_c] if q]

def do_diagnostic():
    rows = []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if not r.get('latitude') or not str(r.get('latitude')).strip():
                rows.append(r)
                
    random.seed(42)
    sample = random.sample(rows, min(20, len(rows)))
    
    normalizer = HotelQueryNormalizer()

    hotels_tested = 0
    queries_generated = 0
    http_successes = 0
    empty_responses = 0
    candidates_returned = 0
    hotels_with_plausible_candidate = 0

    print("=== 20-HOTEL NORMALIZATION DIAGNOSTIC ===")
    
    for row in sample:
        source_name = row.get('name', '').strip()
        source_address = row.get('address', '').strip()
        source_city = extract_city(source_address) or extract_city(row.get('source', ''))
        
        normalized_name, steps = normalizer.normalize(source_name)
        new_queries = normalizer.generate_queries(normalized_name, source_city, source_address)
        old_queries = generate_old_queries(source_name, source_address, source_city)

        hotels_tested += 1
        
        print("\n" + "="*50)
        print("Original hotel:")
        print(f"  - name: {source_name}")
        print(f"  - location/address: {source_address}")
        print(f"  - city: {source_city}")
        print("Normalization Steps:")
        for s in steps:
            print(f"  - {s}")
        print(f"Normalized Name: {normalized_name}")
        print("-" * 50)
        
        print(f"Old Queries: {old_queries}")
        print(f"New Queries: {new_queries}")
        
        candidate_data = []
        for i, q in enumerate(new_queries):
            queries_generated += 1
            print(f"Executing Query {i+1}: {q}")
            res = get_live_response(q)
            if res["error"]:
                print(f"  [HTTP Error: {res['error']}]")
            else:
                print(f"  [HTTP Status: {res['status']}]")
                if res['status'] == 200:
                    http_successes += 1
            
            # Save the cache so we can verify if it works
            cache_file = cache_path(q)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(res["data"], f)
                
            if res["data"]:
                candidate_data = res["data"]
                break
        
        if not candidate_data:
            empty_responses += 1

        candidates_returned += len(candidate_data)
        if candidate_data:
            hotels_with_plausible_candidate += 1
            
        print(f"Nominatim candidates found: {len(candidate_data)}")
        if candidate_data:
            c = candidate_data[0]
            print(f"  - Top candidate name: {c.get('display_name')}")
            print(f"  - Top candidate type: {c.get('type')}")
            print(f"  - Top coords: {c.get('lat')}, {c.get('lon')}")

    print("\n" + "="*50)
    print("=== NORMALIZATION DIAGNOSTIC SUMMARY ===")
    print(f"Hotels tested: {hotels_tested}")
    print(f"Queries generated: {queries_generated}")
    print(f"HTTP URL successes: {http_successes}")
    print(f"Empty responses (0 candidates): {empty_responses}")
    print(f"Candidates returned total: {candidates_returned}")
    print(f"Hotels with >= 1 plausible candidate: {hotels_with_plausible_candidate}")

if __name__ == '__main__':
    do_diagnostic()
