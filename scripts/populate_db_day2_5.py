import pandas as pd
from app.data.database import SessionLocal, engine
from app.data.models import Base, Destination, Attraction, Hotel
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_db_idempotent():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        df_dest = pd.read_csv('datasets/processed/destinations.csv')
        df_attr = pd.read_csv('datasets/processed/attractions.csv')
        df_hot = pd.read_csv('datasets/processed/hotels.csv')
    except Exception as e:
        logger.error(f"Error loading datasets: {e}")
        return

    # Destinations Upsert Loop
    dest_map = {}
    for _, row in df_dest.iterrows():
        dest_name = str(row['destination_name'])
        dest = db.query(Destination).filter_by(destination_name=dest_name).first()
        if not dest:
            dest = Destination(
                destination_name=dest_name,
                state=str(row['state']) if pd.notna(row['state']) else None,
                country=str(row['country']),
                latitude=float(row['latitude']) if pd.notna(row['latitude']) else None,
                longitude=float(row['longitude']) if pd.notna(row['longitude']) else None,
                source=str(row['source']),
                source_record_id=str(row['source_record_id'])
            )
            db.add(dest)
            db.commit()
            db.refresh(dest)
        dest_map[row['destination_id']] = dest.destination_id

    # Attractions Upsert Loop
    for _, row in df_attr.iterrows():
        attr_name = str(row['name'])
        norm_name = str(row['normalized_name'])
        db_dest_id = dest_map.get(row['destination_id'])
        
        if db_dest_id:
            attr = db.query(Attraction).filter_by(normalized_name=norm_name, destination_id=db_dest_id).first()
            if not attr:
                attr = Attraction(
                    name=attr_name,
                    normalized_name=norm_name,
                    destination_id=db_dest_id,
                    latitude=float(row['latitude']) if pd.notna(row['latitude']) else None,
                    longitude=float(row['longitude']) if pd.notna(row['longitude']) else None,
                    currency='INR',
                    source=str(row['source']),
                    source_record_id=str(row['source_record_id']),
                    data_quality_status=str(row['data_quality_status']),
                    coordinate_status=str(row['coordinate_status'])
                )
                db.add(attr)
    db.commit()
    
    # Hotels Upsert Loop
    for _, row in df_hot.iterrows():
        norm_name = str(row['normalized_name'])
        address = str(row['address']) if pd.notna(row['address']) else ""
        
        hot = db.query(Hotel).filter_by(normalized_name=norm_name, address=address).first()
        if not hot:
            hot = Hotel(
                name=str(row['name']),
                normalized_name=norm_name,
                latitude=float(row['latitude']) if pd.notna(row['latitude']) else None,
                longitude=float(row['longitude']) if pd.notna(row['longitude']) else None,
                price_per_night=float(row['price_per_night']) if pd.notna(row['price_per_night']) else None,
                currency='INR',
                rating=float(row['rating']) if pd.notna(row['rating']) else None,
                address=address,
                source=str(row['source']),
                source_record_id=str(row['source_record_id']),
                data_quality_status=str(row['data_quality_status'])
            )
            db_dest_id = dest_map.get(row['destination_id'])
            if pd.notna(row['destination_id']) and db_dest_id:
                hot.destination_id = db_dest_id
            db.add(hot)
    db.commit()
    db.close()
    logger.info("Database populated successfully and idempotently.")

if __name__ == '__main__':
    populate_db_idempotent()
