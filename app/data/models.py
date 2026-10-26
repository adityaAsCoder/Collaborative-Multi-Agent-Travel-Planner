from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Destination(Base):
    __tablename__ = 'destinations'

    destination_id = Column(Integer, primary_key=True, autoincrement=True)
    destination_name = Column(String, nullable=False, unique=True)
    state = Column(String)
    country = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    source = Column(String)
    source_record_id = Column(String)

class Attraction(Base):
    __tablename__ = 'attractions'

    attraction_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    normalized_name = Column(String)
    destination_id = Column(Integer, ForeignKey('destinations.destination_id'))
    category = Column(String)
    subcategory = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    rating = Column(Float)
    review_count = Column(Integer)
    estimated_cost = Column(Float)
    currency = Column(String)
    estimated_visit_duration_min = Column(Integer)
    popularity = Column(Float)
    description = Column(Text)
    
    # Provenance fields
    source = Column(String)
    source_record_id = Column(String)
    source_url = Column(String)
    source_confidence = Column(String)
    retrieved_at = Column(DateTime, default=utc_now_naive)
    coordinate_source = Column(String)
    rating_source = Column(String)
    rating_validation_status = Column(String)
    cost_source = Column(String)
    cost_validation_status = Column(String)
    duration_source = Column(String)
    duration_validation_status = Column(String)
    coordinate_status = Column(String)
    
    data_quality_status = Column(String)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

class Hotel(Base):
    __tablename__ = 'hotels'

    hotel_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    normalized_name = Column(String)
    destination_id = Column(Integer, ForeignKey('destinations.destination_id'))
    latitude = Column(Float)
    longitude = Column(Float)
    price_per_night = Column(Float)
    price_source = Column(String)
    price_source_url = Column(String)
    price_validation_status = Column(String)
    currency = Column(String)
    rating = Column(Float)
    rating_source = Column(String)
    rating_validation_status = Column(String)
    review_count = Column(Integer)
    room_type = Column(String)
    amenities = Column(JSON)
    address = Column(String)
    source = Column(String)
    source_record_id = Column(String)
    source_url = Column(String)
    provenance_source = Column(String)
    data_quality_status = Column(String)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

class TransportSegment(Base):
    __tablename__ = 'transport_segments'

    segment_id = Column(Integer, primary_key=True, autoincrement=True)
    origin_id = Column(Integer)
    destination_id = Column(Integer)
    origin_type = Column(String)
    destination_type = Column(String)
    mode = Column(String)
    distance_km = Column(Float)
    estimated_time_min = Column(Float)
    estimated_cost = Column(Float)
    currency = Column(String)
    source = Column(String)
    graph_version = Column(String)
    calculated_at = Column(DateTime, default=utc_now_naive)

class UserRequest(Base):
    __tablename__ = 'user_requests'

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    destination = Column(String)
    duration = Column(Integer)
    travelers = Column(Integer)
    budget = Column(Float)
    currency = Column(String)
    interests = Column(JSON)
    max_daily_travel_time = Column(Integer)
    accommodation_pref = Column(String)
    created_at = Column(DateTime, default=utc_now_naive)

class Itinerary(Base):
    __tablename__ = 'itineraries'

    itinerary_id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey('user_requests.request_id'))
    day_number = Column(Integer)
    attraction_id = Column(Integer, ForeignKey('attractions.attraction_id'), nullable=True)
    hotel_id = Column(Integer, ForeignKey('hotels.hotel_id'), nullable=True)
    sequence_order = Column(Integer)
    status = Column(String)

class EvaluationLog(Base):
    __tablename__ = 'evaluation_logs'

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    itinerary_id = Column(Integer, ForeignKey('itineraries.itinerary_id'))
    metric_name = Column(String)
    metric_value = Column(Float)
    computed_at = Column(DateTime, default=utc_now_naive)
