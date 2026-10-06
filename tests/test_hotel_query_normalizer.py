import pytest
from app.data.hotel_query_normalizer import HotelQueryNormalizer

def test_normalization_preserves_original():
    normalizer = HotelQueryNormalizer()
    original_name = "Super OYO Capital O King Suites -hennur Near D Mart"
    normalized, steps = normalizer.normalize(original_name)
    assert original_name == "Super OYO Capital O King Suites -hennur Near D Mart"
    assert normalized != original_name

def test_normalization_rules():
    normalizer = HotelQueryNormalizer()
    cases = [
        (
            "Super OYO Capital O King Suites -hennur Near D Mart",
            "King Suites Hennur"
        ),
        (
            "OYO Rooms 604 DB Gupta Main Road 1",
            "Db Gupta Main Road"
        ),
        (
            "SPOT ON Hotel Relax Inn Near Banashankari Metro Station",
            "Hotel Relax Inn"
        ),
        (
            "Collection O 23641 Hotel Cozy Vibes Stay",
            "Hotel Cozy Vibes Stay"
        ),
        (
            "OYO Flagship 80289 Hotel Neha Inn Near Jama Masjid",
            "Hotel Neha Inn Near Jama Masjid"
        )
    ]
    
    for original, expected in cases:
        normalized, steps = normalizer.normalize(original)
        assert normalized == expected, f"Failed on '{original}': got '{normalized}', expected '{expected}'"

def test_query_generation():
    normalizer = HotelQueryNormalizer()
    normalized_name = "King Suites Hennur"
    city = "Bangalore"
    address = "Kalyan Nagar, Bangalore"
    
    queries = normalizer.generate_queries(normalized_name, city, address)
    assert "King Suites Hennur Bangalore" in queries
    assert "King Suites Hennur Kalyan Nagar Bangalore" in queries
