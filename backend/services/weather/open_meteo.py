import logging
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

    async def get_weather(
        self,
        location: Location,
    ) -> Optional[WeatherResponse]:
        """Fetch current weather and 7-day forecast."""

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

            return WeatherResponse(
                current=current_weather,
                hourly=hourly_forecast,
                daily=daily_forecast,
            )

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.error("Open-Meteo request failed: %s", exc)
            return None

open_meteo_service = OpenMeteoService()