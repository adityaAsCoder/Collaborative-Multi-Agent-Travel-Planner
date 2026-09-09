import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.data.models import Base, Destination

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_destination_insertion(db):
    new_dest = Destination(
        destination_name="Udaipur",
        state="Rajasthan",
        latitude=24.5854,
        longitude=73.7125
    )
    db.add(new_dest)
    db.commit()
    db.refresh(new_dest)
    
    assert new_dest.destination_id is not None
    assert new_dest.destination_name == "Udaipur"
    assert new_dest.state == "Rajasthan"
