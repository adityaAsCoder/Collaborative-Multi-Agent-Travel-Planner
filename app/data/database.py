from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLALCHEMY_DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'travel_planner.db').as_posix()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_quality_schema():
    """Add nullable quality metadata without resetting existing local databases."""
    inspector = inspect(engine)
    if inspector.has_table("hotels"):
        columns = {column["name"] for column in inspector.get_columns("hotels")}
        additions = {
            "provenance_source": "VARCHAR",
            "price_source": "VARCHAR",
            "price_source_url": "VARCHAR",
            "price_validation_status": "VARCHAR",
            "rating_source": "VARCHAR",
            "rating_validation_status": "VARCHAR",
        }
        with engine.begin() as connection:
            for name, sql_type in additions.items():
                if name not in columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE hotels ADD COLUMN {name} {sql_type}"
                    )
    if inspector.has_table("attractions"):
        columns = {column["name"] for column in inspector.get_columns("attractions")}
        additions = {
            "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            "rating_validation_status": "VARCHAR",
            "cost_validation_status": "VARCHAR",
            "duration_validation_status": "VARCHAR",
        }
        with engine.begin() as connection:
            for name, sql_type in additions.items():
                if name not in columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE attractions ADD COLUMN {name} {sql_type}"
                    )


ensure_quality_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
