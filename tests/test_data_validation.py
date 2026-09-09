import pytest
import pandas as pd
from app.data.database import SessionLocal
from app.data.models import Attraction, Hotel, Destination

def test_attraction_coordinate_validation():
    try:
        df = pd.read_csv('datasets/processed/attractions.csv')
        valid_coords = df[df['latitude'].notna() & df['longitude'].notna()]
        assert all((valid_coords['latitude'] >= -90) & (valid_coords['latitude'] <= 90))
        assert all((valid_coords['longitude'] >= -180) & (valid_coords['longitude'] <= 180))
    except FileNotFoundError:
        pytest.skip("Dataset not generated yet")

def test_hotel_coordinate_validation():
    try:
        df = pd.read_csv('datasets/processed/hotels.csv')
        valid_coords = df[df['latitude'].notna() & df['longitude'].notna()]
        assert all((valid_coords['latitude'] >= -90) & (valid_coords['latitude'] <= 90))
        assert all((valid_coords['longitude'] >= -180) & (valid_coords['longitude'] <= 180))
    except FileNotFoundError:
        pytest.skip("Dataset not generated yet")

def test_database_insertion_of_processed_records():
    db = SessionLocal()
    dest_count = db.query(Destination).count()
    if dest_count > 0:
        attr_count = db.query(Attraction).count()
        assert attr_count > 0
        hotel_count = db.query(Hotel).count()
        assert hotel_count > 0
    db.close()
