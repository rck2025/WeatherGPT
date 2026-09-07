from unittest.mock import Mock

from backend.schemas import LocationInput
from backend.services.location.resolver import LocationResolver


def test_valid_coordinates_survive_reverse_geocoding_failure() -> None:
    resolver = LocationResolver()
    resolver._reverse_geocode = Mock(return_value=None)
    resolver._ip_fallback = Mock()

    location = resolver.resolve(
        LocationInput(latitude=22.5726, longitude=88.3639, city="Kolkata")
    )

    assert location is not None
    assert location.latitude == 22.5726
    assert location.longitude == 88.3639
    assert location.city == "Kolkata"
    resolver._ip_fallback.assert_not_called()
