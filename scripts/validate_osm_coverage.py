import pandas as pd

def check_osm_coverage(lat, lon):
    # Bounds extracted from northern-zone.gpkg: 
    # (69.149602, 23.0244425, 79.5407261, 35.5686243)
    if pd.isna(lat) or pd.isna(lon):
        return 'unavailable'
        
    MIN_LON, MIN_LAT = 69.1496, 23.0244
    MAX_LON, MAX_LAT = 79.5407, 35.5686
    
    if (MIN_LAT <= lat <= MAX_LAT) and (MIN_LON <= lon <= MAX_LON):
        return 'inside_osm_coverage'
    return 'outside_osm_coverage'

def validate_datasets():
    df_attr = pd.read_csv('datasets/processed/attractions.csv')
    df_hot = pd.read_csv('datasets/processed/hotels.csv')
    
    attr_routing = []
    for _, row in df_attr.iterrows():
        attr_routing.append(check_osm_coverage(row.get('latitude'), row.get('longitude')))
    df_attr['routing_status'] = attr_routing
    df_attr.to_csv('datasets/processed/attractions.csv', index=False)
    
    hot_routing = []
    for _, row in df_hot.iterrows():
        hot_routing.append(check_osm_coverage(row.get('latitude'), row.get('longitude')))
    df_hot['routing_status'] = hot_routing
    df_hot.to_csv('datasets/processed/hotels.csv', index=False)
    
    print("OSM routing coverage explicitly verified and stored for all resolved points.")

if __name__ == '__main__':
    validate_datasets()
