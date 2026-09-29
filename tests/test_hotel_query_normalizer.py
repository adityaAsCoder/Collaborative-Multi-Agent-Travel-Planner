import pytest
from app.data.hotel_query_normalizer import normalize_hotel_query

def test_franchise_prefix_removal():
    original = "Super OYO Capital O King Suites"
    normalized, steps = normalize_hotel_query(original)
    assert normalized == "King Suites"
    assert "removed franchise prefix: Super OYO Capital O" in steps
    assert original == "Super OYO Capital O King Suites" # Original unmodified

def test_oyo_rooms_and_room_number():
    original = "OYO Rooms 604 DB Gupta Main Road 1"
    normalized, steps = normalize_hotel_query(original)
    assert normalized == "DB Gupta Main Road 1"
    assert "removed numeric room/booking metadata: 604" in steps
    assert "removed franchise prefix: OYO Rooms" in steps

def test_promotional_text_preserves_location():
    original = "Hotel Cozy Vibes Near Inderlok Metro Station"
    normalized, steps = normalize_hotel_query(original)
    assert normalized == "Hotel Cozy Vibes Inderlok Metro Station"
    assert "preserved landmark but removed 'near': Inderlok Metro Station" in steps
    # Ensure original is unmodified
    assert original == "Hotel Cozy Vibes Near Inderlok Metro Station"

def test_punctuation_and_whitespace():
    original = "SPOT ON Hotel Relax Inn - Near Banashankari Metro Station"
    normalized, steps = normalize_hotel_query(original)
    assert normalized == "Hotel Relax Inn Banashankari Metro Station"
    
def test_fallback_when_empty():
    original = "OYO 805147"
    normalized, steps = normalize_hotel_query(original)
    # If all is stripped, it might become empty, checking fallback mechanism
    assert normalized == "OYO 805147"
    assert "failed to normalize: string became empty, reverted" in steps

def test_real_example_from_audit():
    original = "Super OYO Capital O King Suites -hennur Near D Mart"
    normalized, steps = normalize_hotel_query(original)
    # Should strip "Super OYO Capital O", "-", "Near D Mart"
    assert normalized == "King Suites hennur"
