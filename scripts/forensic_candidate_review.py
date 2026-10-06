import json
import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from app.data.hotel_query_normalizer import HotelQueryNormalizer
from scripts.resolve_all_hotel_coordinates import progressive_search, name_similarity, map_osm_category, address_match, extract_city, candidate_city, is_generic_name

def analyze_candidates():
    # Read the 20-hotel csv to find which hotels had candidates
    csv_path = Path("datasets/processed/hotel_geocoding_results_diagnostic_20.csv")
    hotels_with_cands = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row.get('candidate_count', 0) or 0) > 0:
                hotels_with_cands.append(row)
                
    normalizer = HotelQueryNormalizer()
    
    results = []
    
    for row in hotels_with_cands:
        hid = row['hotel_id']
        source_name = row['original_hotel_name']
        source_address = row['address']
        source_city = extract_city(source_address) or extract_city(row.get('source', ''))
        
        candidates, final_query, query_variant, norm_name, cache_status, http_status, retry_count = progressive_search(
            source_name, source_city, source_address, normalizer
        )
        
        if candidates:
            for cand in candidates:
                cand_name = extract_candidate_name(cand.get('display_name', ''))
                cand_city = candidate_city(cand)
                cand_type = cand.get('type', '')
                sim = name_similarity(source_name, cand_name)
                city_ok = (source_city.lower() == cand_city.lower()) if source_city and cand_city else False
                addr_ok = address_match(source_address, cand_name)
                type_ok = map_osm_category(cand_type) == "yes"
                
                geo_ok = True
                
                if is_generic_name(source_name):
                    if sim >= 0.90 and city_ok and type_ok and addr_ok:
                        cls = "resolved"
                        rsn = "Generic name met strict thresholds"
                    else:
                        cls = "ambiguous" if city_ok else "rejected"
                        rsn = "Generic name failed strict thresholds"
                else:
                    if sim >= 0.85 and city_ok and type_ok:
                        cls = "resolved"
                        rsn = "High sim, city match, type match"
                    elif sim >= 0.85 and city_ok and addr_ok:
                        cls = "resolved"
                        rsn = "High sim, city match, address match"
                    elif sim >= 0.85 and not city_ok:
                        cls = "rejected" 
                        rsn = "High sim but city mismatch"
                    elif sim < 0.6:
                        cls = "invalid"
                        rsn = "Name similarity too low"
                    else:
                        cls = "rejected"
                        rsn = "Failed matching criteria"
                
                results.append({
                    "hotel_id": hid,
                    "original_name": source_name,
                    "normalized_name": norm_name,
                    "hotel_city": source_city,
                    "hotel_address": source_address,
                    "query_used": final_query,
                    "candidate_name": cand_name,
                    "candidate_city": cand_city,
                    "candidate_lat": cand.get('lat', ''),
                    "candidate_lon": cand.get('lon', ''),
                    "name_sim": f"{sim:.2f}",
                    "city_match": city_ok,
                    "addr_match": addr_ok,
                    "geo_match": geo_ok,
                    "type_match": map_osm_category(cand_type),
                    "cls": cls,
                    "rsn": rsn
                })
                
    with open("forensic_candidates.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    analyze_candidates()
