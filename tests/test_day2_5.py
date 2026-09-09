import pytest
from app.data.database import SessionLocal
from app.data.models import Destination, Attraction, Hotel
import scripts.populate_db_day2_5 as pop

def test_idempotent_etl():
    # Run once
    pop.populate_db_idempotent()
    db = SessionLocal()
    c1 = db.query(Destination).count()
    a1 = db.query(Attraction).count()
    
    # Run twice
    pop.populate_db_idempotent()
    c2 = db.query(Destination).count()
    a2 = db.query(Attraction).count()
    
    assert c1 == c2, "Destination count changed on second run!"
    assert a1 == a2, "Attraction count changed on second run!"
    assert c1 > 0, "No destinations were imported"
    
    # Check no duplicates
    dests = db.query(Destination.destination_name).all()
    names = [d[0] for d in dests]
    assert len(names) == len(set(names)), "Duplicate destination names found"
    
    db.close()
