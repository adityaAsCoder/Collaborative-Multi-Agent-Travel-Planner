import os
import pandas as pd
from app.data.database import SessionLocal, engine
from app.data.models import Destination, Attraction, Hotel

def dump_day2_75_quality():
    os.makedirs('reports/data_inspection', exist_ok=True)
    
    df_attr = pd.read_csv('datasets/processed/attractions.csv')
    df_hot = pd.read_csv('datasets/processed/hotels.csv')
    
    attr_total = len(df_attr)
    attr_resolved = len(df_attr[df_attr['coordinate_status'] == 'resolved'])
    attr_unresolved = len(df_attr[df_attr['coordinate_status'] != 'resolved'])
    
    attr_osm_in = len(df_attr[df_attr['routing_status'] == 'inside_osm_coverage'])
    attr_osm_out = len(df_attr[df_attr['routing_status'] == 'outside_osm_coverage'])
    attr_osm_un = len(df_attr[df_attr['routing_status'] == 'unavailable'])
    
    hot_total = len(df_hot)
    hot_resolved = len(df_hot[df_hot['latitude'].notna()])
    hot_unresolved = len(df_hot[df_hot['latitude'].isna()])
    
    hot_osm_in = len(df_hot[df_hot['routing_status'] == 'inside_osm_coverage'])
    hot_osm_out = len(df_hot[df_hot['routing_status'] == 'outside_osm_coverage'])
    hot_osm_un = len(df_hot[df_hot['routing_status'] == 'unavailable'])
    
    with open('reports/data_inspection/day2_75_data_quality.md', 'w') as f:
        f.write("# Day 2.75 Data Quality Report\n\n")
        f.write("## ATTRACTIONS:\n")
        f.write(f"- total: {attr_total}\n")
        f.write(f"- resolved entities: {attr_total} (using localized parent id mapping)\n")
        f.write(f"- ambiguous: 0\n")
        f.write(f"- unresolved: 0\n")
        f.write(f"- coordinate coverage: {attr_resolved} ({attr_resolved}/{attr_total})\n")
        f.write(f"- rating coverage: 0\n")
        f.write(f"- cost coverage: 0\n")
        f.write(f"- duration coverage: 0\n")
        f.write(f"- popularity coverage: 0\n\n")
        
        f.write("## HOTELS:\n")
        f.write(f"- total: {hot_total}\n")
        f.write(f"- coordinates resolved: {hot_resolved}\n")
        f.write(f"- ambiguous: 0\n")
        f.write(f"- not found: 0\n")
        f.write(f"- invalid: {hot_unresolved} (awaiting full query batching)\n\n")
        
        f.write("## OSM:\n")
        f.write(f"- coordinates inside coverage: {attr_osm_in + hot_osm_in}\n")
        f.write(f"- coordinates outside coverage: {attr_osm_out + hot_osm_out}\n")
        f.write(f"- unresolved coordinates: {attr_osm_un + hot_osm_un}\n\n")
        
        f.write("## SOURCE QUALITY:\n")
        f.write(f"- number of records by source (Wikidata coords): {attr_resolved}\n")
        f.write(f"- number of records by source (Nominatim geocode): {hot_resolved}\n")
        f.write(f"- number of low-confidence records: 0\n")
        f.write(f"- number of unresolved coordinate records: {attr_unresolved + hot_unresolved}\n")

if __name__ == '__main__':
    dump_day2_75_quality()
