import os
import json
import time
import pandas as pd
import requests

def process_day2_5():
    os.makedirs('datasets/processed', exist_ok=True)
    
    # 1. Process Destinations Deterministically
    with open('datasets/raw/tourism/india_tourism_dataset.json', 'r', encoding='utf-8') as f:
        tourism_data = json.load(f)
        
    dest_dict = {}
    attractions = []
    
    for item in tourism_data:
        dest_name = item.get('destination_name', item.get('id', 'Unknown'))
        if dest_name == 'Unknown' and 'state' in item:
             dest_name = f"{item.get('district', '')} {item.get('state', '')}".strip()
             
        norm_dest_name = dest_name.lower().strip()
        coords = item.get('coordinates', {})
        lat = coords.get('latitude')
        lon = coords.get('longitude')
        
        # Deduplicate Destinations
        if norm_dest_name not in dest_dict:
            dest_id = len(dest_dict) + 1
            dest_dict[norm_dest_name] = {
                'destination_id': dest_id,
                'destination_name': dest_name, # keep casing of first encountered
                'state': item.get('state', ''),
                'country': 'India',
                'latitude': lat,
                'longitude': lon,
                'source': 'india_tourism_dataset.json',
                'source_record_id': str(item.get('id', ''))
            }
        
        assigned_dest_id = dest_dict[norm_dest_name]['destination_id']
        
        # Primary attractions 
        pri_attr = item.get('primary_attractions', [])
        for attr_name in pri_attr:
            attractions.append({
                'name': attr_name,
                'normalized_name': attr_name.lower().strip(),
                'destination_id': assigned_dest_id,
                'category': None,
                'subcategory': None,
                'latitude': None,
                'longitude': None,
                'rating': None,
                'review_count': None,
                'estimated_cost': None,
                'currency': 'INR',
                'estimated_visit_duration_min': None,
                'popularity': None,
                'description': None,
                'source': 'india_tourism_dataset.json',
                'source_record_id': str(item.get('id', '')),
                'source_url': None,
                'source_confidence': None,
                'coordinate_source': None,
                'rating_source': None,
                'cost_source': None,
                'duration_source': None,
                'coordinate_status': 'unresolved',
                'data_quality_status': 'missing_data'
            })
            
    df_dest = pd.DataFrame(list(dest_dict.values()))
    
    # Deduplicate Attractions just in case same attraction listed multiple times in same dest
    df_attr = pd.DataFrame(attractions)
    df_attr = df_attr.drop_duplicates(subset=['normalized_name', 'destination_id'], keep='first')
    df_attr['attraction_id'] = range(1, len(df_attr) + 1)
    
    # Save
    df_dest.to_csv('datasets/processed/destinations.csv', index=False)
    df_attr.to_csv('datasets/processed/attractions.csv', index=False)
    
    # Process Hotels
    try:
        df_hotels = pd.read_excel('datasets/raw/hotels/OYO_HOTEL_ROOMS.xlsx')
    except Exception as e:
        print(f"Failed to read hotels xlsx: {e}")
        df_hotels = pd.DataFrame()
        
    hotels_processed = []
    if not df_hotels.empty:
        for idx, row in df_hotels.iterrows():
            orig_name = str(row.get('Hotel_name', ''))
            orig_loc = str(row.get('Location', ''))
            
            if pd.isna(orig_name) or orig_name == 'nan': continue
            
            h_dict = {
                'hotel_id': idx + 1,
                'name': orig_name,
                'normalized_name': orig_name.lower().strip(),
                'destination_id': None, 
                'latitude': None,
                'longitude': None,
                'price_per_night': row.get('Price', None),
                'currency': 'INR',
                'rating': row.get('Rating', None),
                'review_count': None,
                'room_type': 'Standard',
                'amenities': json.dumps({'discount': row.get('Discount', '')}),
                'address': orig_loc,
                'source': 'OYO_HOTEL_ROOMS.xlsx',
                'source_record_id': str(idx),
                'source_url': None,
                'data_quality_status': 'missing_coordinates'
            }
            
            # Match destination mapping by name
            for _, d_row in df_dest.iterrows():
                if isinstance(d_row['destination_name'], str) and d_row['destination_name'].lower() in orig_loc.lower():
                    h_dict['destination_id'] = d_row['destination_id']
                    break
                    
            hotels_processed.append(h_dict)
            
        df_hp = pd.DataFrame(hotels_processed)
        df_hp = df_hp.drop_duplicates(subset=['normalized_name', 'address'], keep='first')
        df_hp['hotel_id'] = range(1, len(df_hp) + 1)
        df_hp.to_csv('datasets/processed/hotels.csv', index=False)

    print("Data processing pipeline complete for Day 2.5. Deterministic rows stored.")

if __name__ == '__main__':
    process_day2_5()
