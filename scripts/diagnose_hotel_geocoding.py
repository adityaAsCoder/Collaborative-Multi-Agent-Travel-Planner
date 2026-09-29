#!/usr/bin/env python3
import warnings
import urllib3
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
import csv
import json
import time
import hashlib
from pathlib import Path
from difflib import SequenceMatcher
import requests
import random
import sys
import os

# Add project root to sys path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.data.hotel_query_normalizer import normalize_hotel_query

DATA_PATH = Path("datasets/processed/hotels.csv")
CACHE_DIR = Path(".cache")
USER_AGENT = "TravelPlanner/2.9.2 (contact: debug@travelplanner.example)"

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
        # Give it a reasonable timeout but if it's blackholed it will fail.
        # We will log the exact failure.
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

def do_diagnostic():
    rows = []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if not r.get('latitude') or not str(r.get('latitude')).strip():
                rows.append(r)
                
    random.seed(42)
    sample = random.sample(rows, min(20, len(rows)))
    
    print("=== 20-HOTEL DIAGNOSTIC SAMPLE ===")
    
    for row in sample:
        source_name = row.get('name', '').strip()
        source_address = row.get('address', '').strip()
        source_city = extract_city(source_address) or extract_city(row.get('source', ''))
        
        print(f"\nOriginal hotel:")
        print(f"  - name: {source_name}")
        print(f"  - location/address: {source_address}")
        print(f"  - city: {source_city}")
        
        
        queries = {"Old Query": [], "New Query": []}
        
        q_a_old = f"{source_name} {source_city}".strip()
        q_b_old = f"{source_name}, {source_address}, {source_city}".strip()
        locality = ""
        if source_address and "," in source_address:
            parts = [p.strip() for p in source_address.split(",")]
            if len(parts) > 1:
                locality = parts[0]
        q_c_old = f"{source_name} {locality} {source_city}".strip() if locality else ""
        queries["Old Query"] = [x for x in [q_a_old, q_b_old, q_c_old] if x]
        
        normalized_name, steps = normalize_hotel_query(source_name)
        q_a_new = f"{normalized_name} {source_city}".strip()
        q_b_new = f"{normalized_name}, {source_address}, {source_city}".strip()
        q_c_new = f"{normalized_name} {locality} {source_city}".strip() if locality else ""
        queries["New Query"] = [x for x in [q_a_new, q_b_new, q_c_new] if x]
        
        for q_type, q_list in queries.items():
            candidate_data = []
            print(f"\n--- {q_type} Type ---")
            for i, q in enumerate(q_list):
                print(f"Query {i+1}: {q}")
                res = get_live_response(q)
                if res["error"]:
                    print(f"  HTTP Error: {res['error']}")
                else:
                    print(f"  HTTP Status: {res['status']}")
                
                cache_file = cache_path(q)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(res["data"], f)
                    
                if res["data"]:
                    candidate_data = res["data"]
                    break
            
            print(f"Nominatim candidates found: {len(candidate_data)}")
            if candidate_data:
                c = candidate_data[0]
                print(f"  candidate name: {c.get('display_name')}")
                print(f"  candidate type: {c.get('type')}")
                print(f"  coords: {c.get('lat')}, {c.get('lon')}")
                
        print(f"Normalization steps: {steps}")
            
if __name__ == '__main__':
    do_diagnostic()
