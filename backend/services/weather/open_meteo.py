import asyncio
import logging
import os
import time
from typing import Optional

import httpx

from backend.schemas import (
    Location,
    WeatherResponse,
    CurrentWeatherData,
    HourlyForecast,
    DailyForecast,
)

logger = logging.getLogger(__name__)


class OpenMeteoService:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    # India-only application
    TIMEZONE = "Asia/Kolkata"

    HEADERS = {
        "User-Agent": "WeatherGPT_SIH_Project_Contact@team.com"
    }

    def __init__(self, cache_ttl_seconds: int | None = None) -> None:
        # Open-Meteo's public endpoint is shared by every Render instance using
        # the same outbound IP.  Cache the *complete* forecast, rather than
        # only current conditions, so a chat conversation does not repeatedly
        # make the same relatively expensive request.
        self.cache_ttl_seconds = cache_ttl_seconds or int(
            os.getenv("WEATHER_CACHE_TTL_SECONDS", "600")
        )
        self._cache: dict[tuple[float, float], tuple[float, WeatherResponse]] = {}
        self._locks: dict[tuple[float, float], asyncio.Lock] = {}

    @staticmethod
    def _cache_key(location: Location) -> tuple[float, float]:
        # Roughly 11 m precision: location resolver results remain stable and
        # nearby repeat requests coalesce without mixing distinct cities.
        return (round(location.latitude, 4), round(location.longitude, 4))

    def _fresh_cache_entry(self, key: tuple[float, float]) -> WeatherResponse | None:
        entry = self._cache.get(key)
        if entry and time.monotonic() - entry[0] < self.cache_ttl_seconds:
            return entry[1]
        return None

    async def get_weather(
        self,
        location: Location,
    ) -> Optional[WeatherResponse]:
        """Fetch current weather and 7-day forecast."""

        key = self._cache_key(location)
        cached = self._fresh_cache_entry(key)
        if cached is not None:
            return cached

        # A per-location lock prevents a burst of identical chats from making
        # identical upstream calls before the first response reaches the cache.
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._fresh_cache_entry(key)
            if cached is not None:
                return cached
            return await self._fetch_weather(location, key)

    async def _fetch_weather(
        self,
        location: Location,
        key: tuple[float, float],
    ) -> Optional[WeatherResponse]:
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": self.TIMEZONE,
            "forecast_days": 7,

            # Fields available in CurrentWeatherData
            "current": [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m",
                "weather_code",
            ],

            # Fields available in HourlyForecast
            "hourly": [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m",
                "weather_code",
            ],

            # Fields available in DailyForecast
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "weather_code",
            ],
        }

        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=10,
            ) as client:
                response = await client.get(
                    self.BASE_URL,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            current = data["current"]
            hourly = data["hourly"]
            daily = data["daily"]

            # Current weather
            current_weather = CurrentWeatherData(
                temperature=current.get("temperature_2m"),
                feels_like=current.get("apparent_temperature"),
                humidity=current.get("relative_humidity_2m"),
                precipitation=current.get("precipitation"),
                wind_speed=current.get("wind_speed_10m"),
                weather_code=current.get("weather_code"),
            )

            # 48 hourly forecasts, then every 6 hours
            hourly_forecast = []

            for i, timestamp in enumerate(hourly["time"]):
                if i < 48 or (i >= 48 and (i - 48) % 6 == 0):
                    hourly_forecast.append(
                        HourlyForecast(
                            timestamp=timestamp,
                            temperature=hourly["temperature_2m"][i],
                            feels_like=hourly["apparent_temperature"][i],
                            humidity=hourly["relative_humidity_2m"][i],
                            precipitation=hourly["precipitation"][i],
                            wind_speed=hourly["wind_speed_10m"][i],
                            weather_code=hourly["weather_code"][i],
                        )
                    )

            # 7-day daily forecast
            daily_forecast = []

            for i, date in enumerate(daily["time"]):
                daily_forecast.append(
                    DailyForecast(
                        date=date,
                        temperature_max=daily["temperature_2m_max"][i],
                        temperature_min=daily["temperature_2m_min"][i],
                        precipitation=daily["precipitation_sum"][i],
                        weather_code=daily["weather_code"][i],
                    )
                )

            weather = WeatherResponse(
                current=current_weather,
                hourly=hourly_forecast,
                daily=daily_forecast,
            )
            self._cache[key] = (time.monotonic(), weather)
            return weather

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            # If Open-Meteo has rate-limited the shared deployment IP, serving
            # the last good value is more useful than making every chat fail.
            stale = self._cache.get(key)
            if stale is not None:
                logger.warning("Open-Meteo request failed; serving stale cached weather: %s", exc)
                return stale[1]
            logger.error("Open-Meteo request failed: %s", exc)
            return None

open_meteo_service = OpenMeteoService()
