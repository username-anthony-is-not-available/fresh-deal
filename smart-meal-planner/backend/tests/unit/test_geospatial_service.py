
import pytest
from app.services.geospatial_service import GeospatialService

def test_get_coordinates_valid():
    coords = GeospatialService.get_coordinates("H4T 1V6")
    assert coords == (45.4954, -73.6798)

def test_get_coordinates_lowercase():
    coords = GeospatialService.get_coordinates("h4t 1v6")
    assert coords == (45.4954, -73.6798)

def test_get_coordinates_invalid():
    coords = GeospatialService.get_coordinates("XYZ 123")
    assert coords is None

def test_calculate_distance():
    # Distance between H4T (45.4954, -73.6798) and H4E (45.4542, -73.5855)
    # Approx 8.7 km
    dist = GeospatialService.calculate_distance(45.4954, -73.6798, 45.4542, -73.5855)
    assert 8.6 < dist < 8.8

def test_get_distance_between_postal_codes():
    dist = GeospatialService.get_distance_between_postal_codes("H4T1V6", "H4E2G9")
    assert dist is not None
    assert 8.6 < dist < 8.8

def test_get_distance_between_postal_codes_none():
    dist = GeospatialService.get_distance_between_postal_codes("H4T1V6", "INVALID")
    assert dist is None
