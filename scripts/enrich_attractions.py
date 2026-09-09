import os
import json
import time
import requests
import pandas as pd

CACHE_FILE = 'datasets/processed/wikidata_cache.json'

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def search_wikidata(name, destination):
    url = "https://www.wikidata.org/w/api.php"
    query = f"{name} {destination}"
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "search": query,
        "limit": 1
    }
    headers = {"User-Agent": "TravelPlannerDataPipeline/1.0 (contact@example.com)"}
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('search'):
                return data['search'][0]['id']
    except Exception as e:
        print(f"Wikidata search error: {e}")
    return None

def get_wikidata_attributes(q_id):
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": q_id,
        "props": "claims"
    }
    headers = {"User-Agent": "TravelPlannerDataPipeline/1.0"}
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            claims = data.get('entities', {}).get(q_id, {}).get('claims', {})
            
            lat, lon = None, None
            # P625 = coordinate location
            if 'P625' in claims:
                try:
                    val = claims['P625'][0]['mainsnak']['datavalue']['value']
                    lat, lon = val['latitude'], val['longitude']
                except: pass
                
            return {
                'latitude': lat,
                'longitude': lon,
                'duration': None, # P2047 duration rarely populated
                'cost': None      # P2555 fee rarely populated
            }
    except Exception:
        pass
    return None

def enrich_attractions():
    cache = load_cache()
    df_attr = pd.read_csv('datasets/processed/attractions.csv')
    df_dest = pd.read_csv('datasets/processed/destinations.csv')
    
    enriched = 0
    max_to_process = 10 # Hard limit for safety in automated runs
    
    for idx, row in df_attr.iterrows():
        if row['coordinate_status'] == 'resolved':
            continue
            
        attr_name = row['name']
        dest_id = row['destination_id']
        dest_name = df_dest[df_dest['destination_id'] == dest_id]['destination_name'].values[0]
        
        cache_key = f"{attr_name}::{dest_name}"
        
        if cache_key not in cache:
            if enriched >= max_to_process:
                break
                
            q_id = search_wikidata(attr_name, dest_name)
            time.sleep(1) # rate limit
            
            if q_id:
                attrs = get_wikidata_attributes(q_id)
                time.sleep(1)
                cache[cache_key] = {
                    'q_id': q_id,
                    'attrs': attrs
                }
            else:
                cache[cache_key] = {'q_id': None, 'attrs': None}
            enriched += 1
            save_cache(cache)
            
        c = cache[cache_key]
        if c.get('q_id') and c.get('attrs') and c['attrs'].get('latitude'):
            df_attr.at[idx, 'latitude'] = c['attrs']['latitude']
            df_attr.at[idx, 'longitude'] = c['attrs']['longitude']
            df_attr.at[idx, 'coordinate_source'] = f"Wikidata: {c['q_id']}"
            df_attr.at[idx, 'coordinate_status'] = 'resolved'
            df_attr.at[idx, 'coordinate_confidence'] = 'high'
        else:
            df_attr.at[idx, 'coordinate_status'] = 'unresolved'
            
    df_attr.to_csv('datasets/processed/attractions.csv', index=False)
    print(f"Enriched {enriched} new attractions.")

if __name__ == '__main__':
    enrich_attractions()
