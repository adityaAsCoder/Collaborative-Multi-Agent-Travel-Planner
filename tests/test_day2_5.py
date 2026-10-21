import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.data.models import Attraction, Base, Destination, Hotel
import scripts.populate_db_day2_5 as pop


def test_idempotent_etl_uses_isolated_database_and_csvs(tmp_path):
    destinations = pd.DataFrame([{
        "destination_id": 1,
        "destination_name": "Jaipur",
        "state": "Rajasthan",
        "country": "India",
        "latitude": 26.9,
        "longitude": 75.8,
    }])
    attractions = pd.DataFrame([{
        "attraction_id": 44,
        "name": "City Palace",
        "destination_id": 1,
        "latitude": "",
        "longitude": "",
        "estimated_cost": "",
    }])
    hotels = pd.DataFrame([{
        "hotel_id": 8,
        "name": "Example Jaipur Hotel",
        "address": "Jaipur, Rajasthan",
        "price_per_night": "",
    }])
    paths = []
    for name, frame in (
        ("destinations.csv", destinations),
        ("attractions.csv", attractions),
        ("hotels.csv", hotels),
    ):
        path = tmp_path / name
        frame.to_csv(path, index=False)
        paths.append(path)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    args = {
        "destinations_path": paths[0],
        "attractions_path": paths[1],
        "hotels_path": paths[2],
        "session_factory": session_factory,
        "db_engine": engine,
    }
    first = pop.populate_db_idempotent(**args)
    second = pop.populate_db_idempotent(**args)
    assert first["destinations_upserted"] == second["destinations_upserted"] == 1
    assert first["attractions_activated"] == second["attractions_activated"] == 1
    assert first["hotels_upserted"] == second["hotels_upserted"] == 1

    with session_factory() as db:
        assert db.query(Destination).count() == 1
        assert db.query(Attraction).count() == 1
        assert db.query(Hotel).count() == 1
        assert db.query(Attraction).first().estimated_cost is None
        assert db.query(Hotel).first().price_per_night is None
    engine.dispose()
