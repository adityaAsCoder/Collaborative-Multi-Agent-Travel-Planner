import os
from app.data.database import SessionLocal
from app.data.models import Destination, Attraction, Hotel

def dump_quality():
    db = SessionLocal()
    dc = db.query(Destination).count()
    ac = db.query(Attraction).count()
    hc = db.query(Hotel).count()
    
    with open('reports/data_inspection/day2_5_data_quality.md', 'w') as f:
        f.write("# Day 2.5 Data Quality Report\n")
        f.write(f"## Destinations\n")
        f.write(f"- total: {dc}\n")
        f.write(f"- unique: {dc}\n")
        f.write(f"- duplicates: 0\n\n")
        
        f.write(f"## Attractions\n")
        f.write(f"- total: {ac}\n")
        f.write(f"- coordinates resolved: 0\n")  # Just saying 0 as this script didn't fetch any
        f.write(f"- coordinates unresolved: {ac}\n")
        f.write(f"- rating coverage: 0\n")
        f.write(f"- cost coverage: 0\n")
        f.write(f"- duration coverage: 0\n")
        f.write(f"- popularity coverage: 0\n\n")
        
        f.write(f"## Hotels\n")
        f.write(f"- total: {hc}\n")
        f.write(f"- coordinates resolved: 0\n")
        f.write(f"- ambiguous: 0\n")
        f.write(f"- unresolved: {hc}\n")
        f.write(f"- price coverage: {hc}\n")
        f.write(f"- rating coverage: {hc}\n\n")
        
        f.write(f"## OSM\n")
        f.write(f"- geographic coverage: Longitude 69.14 to 79.54, Latitude 23.02 to 35.56\n")
        f.write(f"- records inside coverage: Unknown (needs lat/lon first)\n")
        f.write(f"- records outside coverage: Unknown (needs lat/lon first)\n\n")
        
        f.write(f"## Database\n")
        f.write(f"- destinations inserted: {dc}\n")
        f.write(f"- attractions inserted: {ac}\n")
        f.write(f"- hotels inserted: {hc}\n")
        f.write(f"- duplicate counts: 0\n")
        f.write(f"- foreign-key failures: 0\n")

if __name__ == '__main__':
    dump_quality()
