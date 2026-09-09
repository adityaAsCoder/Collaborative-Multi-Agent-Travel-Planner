import os
import pandas as pd
from app.data.database import SessionLocal, engine
from app.data.models import Destination, Attraction, Hotel

def audit():
    os.makedirs('reports/data_inspection', exist_ok=True)
    report = ["# Day 2.5 Audit Report\n"]
    
    try:
        dest_df = pd.read_csv('datasets/processed/destinations.csv')
        attr_df = pd.read_csv('datasets/processed/attractions.csv')
        hot_df = pd.read_csv('datasets/processed/hotels.csv')
        
        report.append("## Raw CSV Row Counts")
        report.append(f"- destinations.csv: {len(dest_df)}")
        report.append(f"- attractions.csv: {len(attr_df)}")
        report.append(f"- hotels.csv: {len(hot_df)}\n")
        
        report.append("## Destination Duplicates (Normalized)")
        norm_dests = dest_df['destination_name'].str.lower().str.strip()
        duplicates = norm_dests.duplicated().sum()
        report.append(f"- Duplicate destination names: {duplicates}\n")
        
        report.append("## Missing value percentages")
        for name, df in [('Attractions', attr_df), ('Hotels', hot_df)]:
            report.append(f"### {name}")
            for col in df.columns:
                pct = df[col].isna().sum() / len(df) * 100
                report.append(f"- {col}: {pct:.1f}% missing")
            report.append("")
            
    except Exception as e:
        report.append(f"Error reading datasets: {e}\n")
        
    try:
        db = SessionLocal()
        dest_count = db.query(Destination).count()
        attr_count = db.query(Attraction).count()
        hot_count = db.query(Hotel).count()
        
        report.append("## Current Database Population")
        report.append(f"- Destinations: {dest_count}")
        report.append(f"- Attractions: {attr_count}")
        report.append(f"- Hotels: {hot_count}\n")
    except Exception as e:
        report.append(f"Database error (likely not populated): {e}\n")
        
    with open('reports/data_inspection/day2_5_audit.md', 'w') as f:
        f.write('\n'.join(report))
        
if __name__ == '__main__':
    audit()
