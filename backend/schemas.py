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


class Minutely15Forecast(BaseModel):
    timestamp: datetime
    precipitation: float | None = None
    weather_code: int | None = None
    rain: float | None = None


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
    minutely_15: list[Minutely15Forecast] = []


# -------------------------
# ALERTS
# -------------------------

class WeatherAlert(BaseModel):
    title: str
    description: str
    severity: str
    source: str
    latitude: float | None = None
    longitude: float | None = None
    is_historical: bool = False
    occurred_at: datetime | None = None
    lightning_active: bool = False
    magnitude: float | None = None
    visual_radius: float | None = None


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
    scientific_mode: bool = False
    history: list[dict] = []


# -------------------------
# SYNOPTIC OVERLAYS
# -------------------------

class SynopticOverlay(BaseModel):
    name: str
    type: str = "low-pressure"
    bounds: list[list[float]]
    center: list[float] | None = None
    severity: str = "High"
    description: str | None = None


# -------------------------
# CHAT RESPONSE
# -------------------------

class ChatResponse(BaseModel):
    bot_reply: str
    location: Location | None = None
    weather: WeatherResponse | None = None
    alerts: list[WeatherAlert] = []
    sources: list[RAGDocument] = []
    synoptic_overlays: list[SynopticOverlay] = []
    audio_url: str | None = None
    audio_base64: str | None = None
    transcribed_query: str | None = None
    detected_language: str | None = None
    history_data: list[HourlyForecast] = []
    transcription_method: str | None = "Whisper"
    transcription_confidence: float | None = None
    locked_language_code: str | None = None
    confidence_score: float = 1.0
    model_disagreement: bool = False


# -------------------------
# FULL PIPELINE RESPONSE (SIH Demo & Voice Pipeline Contract)
# -------------------------

class FullPipelineResponse(BaseModel):
    bot_reply: str
    location: Location | None = None
    weather: WeatherResponse | None = None
    alerts: list[WeatherAlert] = []
    sources: list[RAGDocument] = []
    synoptic_overlays: list[SynopticOverlay] = []
    audio_url: str | None = None
    audio_base64: str | None = None
    transcribed_query: str | None = None
    detected_language: str | None = None
    history_data: list[HourlyForecast] = []
    transcription_method: str | None = "Whisper"
    transcription_confidence: float | None = None
    locked_language_code: str = "en"
    confidence_score: float = 1.0
    model_disagreement: bool = False

