from datetime import datetime
from pydantic import BaseModel, Field


# -------------------------
# LOCATION
# -------------------------

class LocationInput(BaseModel):
    latitude: float | None = None
    longitude: float | None = None

    city: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None

    raw_text: str | None = None


class Location(BaseModel):
    latitude: float
    longitude: float
    timezone: str | None = None

    city: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None


# -------------------------
# WEATHER
# -------------------------

class CurrentWeatherData(BaseModel):
    temperature: float | None = None
    feels_like: float | None = None
    humidity: float | None = None
    precipitation: float | None = None
    wind_speed: float | None = None
    weather_code: int | None = None


class HourlyForecast(BaseModel):
    timestamp: datetime
    temperature: float | None = None
    feels_like: float | None = None
    humidity: float | None = None
    precipitation: float | None = None
    wind_speed: float | None = None
    weather_code: int | None = None


class DailyForecast(BaseModel):
    date: datetime
    temperature_max: float | None = None
    temperature_min: float | None = None
    precipitation: float | None = None
    weather_code: int | None = None


class WeatherResponse(BaseModel):
    current: CurrentWeatherData | None = None
    hourly: list[HourlyForecast] = []
    daily: list[DailyForecast] = []


# -------------------------
# ALERTS
# -------------------------

class WeatherAlert(BaseModel):
    title: str
    description: str
    severity: str
    source: str


# -------------------------
# RAG
# -------------------------

class RAGDocument(BaseModel):
    content: str
    source: str
    score: float | None = None


# -------------------------
# CHAT REQUEST
# -------------------------

class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    location: LocationInput | None = None
    language: str = "en"
    channel: str = "web"


# -------------------------
# CHAT RESPONSE
# -------------------------

class ChatResponse(BaseModel):
    bot_reply: str
    location: Location | None = None
    weather: WeatherResponse | None = None
    alerts: list[WeatherAlert] = []
    sources: list[RAGDocument] = []
    audio_url: str | None = None