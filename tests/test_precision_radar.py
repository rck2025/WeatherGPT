"""
Tests for Precision Radar Upgrade & Confidence-Based Multi-Source Data Fusion.
Verifies:
1. extract_minute_offset parsing 1-minute and 5-minute queries across multiple Indic scripts.
2. Observational microscope service: get_radar_nowcast and get_ground_truth.
3. Multi-source data fusion in WeatherGPTBrain:
   - < 30 min queries prioritize live IMD Doppler Weather Radar (DWR) over Open-Meteo dry predictions.
   - Radar override delivers 99% confidence warning for 1-minute queries.
   - Citations include SOURCE_CONFIDENCE tags for both Radar (99%) and NWP (70%).
"""
from datetime import datetime, timedelta
import pytest

from backend.schemas import (
    Location,
    WeatherResponse,
    CurrentWeatherData,
    Minutely15Forecast,
    ChatRequest,
)
from backend.services.weather.observational import (
    get_radar_nowcast,
    get_ground_truth,
    IMD_DWR_RADAR_NETWORK,
)
from backend.services.rag.brain import extract_minute_offset
from backend.services.rag.service import WeatherGPTBrain


# ------------------------------------------------------------------
# 1. 1-MINUTE TEMPORAL PARSER
# ------------------------------------------------------------------
def test_extract_minute_offset_ultra_short():
    assert extract_minute_offset("Will it rain in 1 minute?") == 1
    assert extract_minute_offset("Will it rain in 1 min?") == 1
    assert extract_minute_offset("Will it rain in one minute?") == 1
    assert extract_minute_offset("kya 1 minute mein barish hogi?") == 1
    assert extract_minute_offset("১ মিনিট এ বৃষ্টি হবে?") == 1
    assert extract_minute_offset("१ मिनिटात पाऊस पडेल काय?") == 1
    assert extract_minute_offset("Will it rain in 5 minutes?") == 5
    assert extract_minute_offset("Any rain in 15 mins?") == 15
    assert extract_minute_offset("Will it rain in 2 hours?") == 120


# ------------------------------------------------------------------
# 2. OBSERVATIONAL MICROSCOPE SERVICE
# ------------------------------------------------------------------
def test_get_radar_nowcast_confidence():
    # 1-minute query gets 99% tactical confidence
    radar_1m = get_radar_nowcast(22.5726, 88.3639, offset_mins=1)
    assert radar_1m["source"] == "IMD Doppler Weather Radar (DWR)"
    assert radar_1m["confidence"] == 0.99
    assert radar_1m["status"] == "PRECIPITATION_DETECTED"
    assert "DWR Kolkata" in radar_1m["radar_station"]
    assert radar_1m["reflectivity_dbz"] >= 40.0

    # 20-minute query gets standard tracking confidence (88%)
    radar_20m = get_radar_nowcast(19.0760, 72.8777, offset_mins=20)
    assert radar_20m["confidence"] == 0.88
    assert "DWR Mumbai" in radar_20m["radar_station"]


def test_get_ground_truth():
    ground = get_ground_truth(22.5726, 88.3639)
    assert "AWS" in ground["source"]
    assert ground["surface_rain_detected"] is True
    assert ground["confidence"] >= 0.95


# ------------------------------------------------------------------
# 3. MULTI-SOURCE DATA FUSION: 1-MINUTE RADAR OVERRIDE
# ------------------------------------------------------------------
def test_radar_overrides_numerical_dry_model_for_1_minute():
    brain = WeatherGPTBrain()
    now = datetime.now()

    # Open-Meteo numerical model predicts 0.0mm (dry conditions)
    dry_intervals = [
        Minutely15Forecast(timestamp=now + timedelta(minutes=15), precipitation=0.0, weather_code=0, rain=0.0),
        Minutely15Forecast(timestamp=now + timedelta(minutes=30), precipitation=0.0, weather_code=0, rain=0.0),
    ]
    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=32.0, humidity=65, wind_speed=8.0, precipitation=0.0),
        minutely_15=dry_intervals,
    )
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")
    req = ChatRequest(query="Will it rain in 1 minute in Kolkata?")

    resp = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[])
    reply = resp["bot_reply"]

    # The AI or deterministic fallback MUST confirm rain using the tactical radar sweep
    # and explain that while the numerical model predicted dry, radar sees an active cell!
    assert "Radar" in reply or "radar" in reply or "PRECIPITATION" in reply or "rain" in reply.lower()
    assert "IMD Doppler Weather Radar" in reply or "DWR" in reply
    assert "Confidence" in reply or "99%" in reply or "shelter" in reply.lower()

    # Sources must contain IMD Doppler Radar with 99% confidence badge
    radar_source = next((s for s in resp["sources"] if "Doppler" in s["source"] and "Radar" in s["source"]), None)
    assert radar_source is not None
    assert "99%" in radar_source["source"]


# ------------------------------------------------------------------
# 4. LONG-RANGE QUERY (>= 30 MINS) PRIORITIZES NUMERICAL NWP
# ------------------------------------------------------------------
def test_long_range_query_prioritizes_numerical_model():
    brain = WeatherGPTBrain()
    now = datetime.now()

    # Rain predicted at +45 min (2.8mm)
    intervals = [
        Minutely15Forecast(timestamp=now + timedelta(minutes=15), precipitation=0.0, weather_code=0, rain=0.0),
        Minutely15Forecast(timestamp=now + timedelta(minutes=30), precipitation=0.0, weather_code=0, rain=0.0),
        Minutely15Forecast(timestamp=now + timedelta(minutes=45), precipitation=2.8, weather_code=61, rain=2.8),
    ]
    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=30.0, humidity=70, wind_speed=12.0, precipitation=0.0),
        minutely_15=intervals,
    )
    loc = Location(latitude=19.0760, longitude=72.8777, city="Mumbai")
    req = ChatRequest(query="Will it rain in the next 45 minutes in Mumbai?")

    resp = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[])
    reply = resp["bot_reply"]

    # 45-minute query should use NWP minutely intervals
    assert "NWP High-Resolution Minutely Model" in reply or "45 minutes" in reply or "2.8" in reply
