import asyncio
import time
from unittest.mock import AsyncMock

from backend.schemas import Location, WeatherResponse
from backend.services.weather.open_meteo import OpenMeteoService


def test_weather_response_is_cached_per_location_for_ttl() -> None:
    async def run() -> None:
        service = OpenMeteoService(cache_ttl_seconds=600)
        weather = WeatherResponse()

        async def fake_fetch(_location, key):
            service._cache[key] = (time.monotonic(), weather)
            return weather

        service._fetch_weather = AsyncMock(side_effect=fake_fetch)
        location = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")

        assert await service.get_weather(location) is not None
        assert await service.get_weather(location) is not None
        service._fetch_weather.assert_awaited_once()

    asyncio.run(run())
