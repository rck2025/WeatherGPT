"""
Test Suite for Temporal Directionality: Past vs Future Minute-Level Nowcasts.
Validates 'Ago' vs 'In' routing, signed minute offsets, AWS ground-truth citations,
and memory leak isolation (stripping forward nowcasts/alerts from historical queries).
"""

from datetime import datetime, timedelta
import pytest

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    Location,
    Minutely15Forecast,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.brain import parse_dynamic_time
from backend.services.rag.service import WeatherGPTBrain, detect_temporal_intent


# ------------------------------------------------------------------
# 1. PARSE DYNAMIC TIME SIGNED PARSING
# ------------------------------------------------------------------
def test_parse_dynamic_time_past_markers():
    """Verify that 'ago', 'previous', 'last', and Indic past words return negative offsets."""
    assert parse_dynamic_time("30 mins ago") == -30
    assert parse_dynamic_time("Was it raining in the previous 30 mins?") == -30
    assert parse_dynamic_time("Did it rain in the last 15 minutes in Kolkata?") == -15
    assert parse_dynamic_time("what was the weather 10 minutes ago") == -10
    assert parse_dynamic_time("in the past 45 minutes") == -45

    # Indic languages past markers
    assert parse_dynamic_time("15 minute pehle kya barish thi?") == -15  # Hindi / Urdu
    assert parse_dynamic_time("beete 30 minute mein barish") == -30       # Hindi
    assert parse_dynamic_time("১৫ মিনিট আগে বৃষ্টি হয়েছিল কি?") == -15   # Bengali
    assert parse_dynamic_time("मागील ३० मिनिटात पाऊस पडला का?") == -30   # Marathi
    assert parse_dynamic_time("30 நிமிடங்களுக்கு முன்பு மழை பெய்ததா?") == -30  # Tamil


def test_parse_dynamic_time_future_markers():
    """Verify that 'in', 'next', and Indic future words return positive offsets."""
    assert parse_dynamic_time("In 30 mins") == 30
    assert parse_dynamic_time("Will it rain in 1 minute in Kolkata?") == 1
    assert parse_dynamic_time("next 15 minutes") == 15
    assert parse_dynamic_time("rain in the next 45 minutes") == 45
    assert parse_dynamic_time("agle 30 minute mein barish hogi?") == 30  # Hindi
    assert parse_dynamic_time("পরবর্তী ১৫ মিনিটে বৃষ্টি হবে?") == 15      # Bengali


def test_detect_temporal_intent_direction():
    """Verify detect_temporal_intent classifies negative offsets as 'past' and positive as 'nowcast'."""
    assert detect_temporal_intent("Was it raining in the previous 30 mins?") == "past"
    assert detect_temporal_intent("Did it rain 15 minutes ago in Mumbai?") == "past"
    assert detect_temporal_intent("Will it rain in the next 15 minutes in Mumbai?") == "nowcast"
    assert detect_temporal_intent("Will it rain in 1 minute in Kolkata?") == "nowcast"


# ------------------------------------------------------------------
# 2. HISTORICAL ROUTING FOR PREVIOUS 30 MINS
# ------------------------------------------------------------------
def test_past_query_routes_to_ground_truth_and_suppresses_alerts():
    """
    Validation Test from Specification:
    When asking: 'Was it raining in the previous 30 mins in Mumbai?', the bot must:
    1. Answer using ground sensors (e.g. 'According to ground sensors, no rain was recorded in the last 30 minutes (0.0mm recorded).').
    2. Zero mention of forward nowcasts (e.g. 'Next 3 hours', 'predicted', 'forecast').
    3. CITE: 'Source: MoES Ground-Truth Sensors (AWS)'.
    4. Strip active alerts (no EMERGENCY WARNING for storms that already passed).
    """
    brain = WeatherGPTBrain()
    now = datetime.now()

    # Create dummy active alerts and future nowcast that MUST be stripped
    active_nowcast_alert = WeatherAlert(
        title="🚨 URGENT NOWCAST: Severe Thunderstorm Imminent in Next 3 Hours",
        description="Dangerous squall line approaching Mumbai.",
        severity="High",
        source="IMD Doppler Weather Radar",
    )
    future_rain_intervals = [
        Minutely15Forecast(timestamp=now + timedelta(minutes=15), precipitation=4.5, weather_code=65, rain=4.5),
        Minutely15Forecast(timestamp=now + timedelta(minutes=30), precipitation=6.0, weather_code=65, rain=6.0),
    ]
    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=31.0, humidity=80, wind_speed=25.0, precipitation=0.0),
        minutely_15=future_rain_intervals,
    )
    loc = Location(latitude=19.0760, longitude=72.8777, city="Mumbai")
    req = ChatRequest(query="Was it raining in the previous 30 mins in Mumbai?")

    resp = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[active_nowcast_alert])
    reply = resp["bot_reply"]

    # 1. Ground sensors report
    assert "ground sensor" in reply.lower() or "records show" in reply.lower() or "0.0" in reply or "no rain" in reply.lower()
    assert "MoES Ground-Truth Sensors (AWS)" in reply or "Ground-Truth Sensors" in reply

    # 2. Forward nowcasts and forecast terms suppressed
    assert "Next 3 hours" not in reply
    assert "predicted to start" not in reply.lower()

    # 3. Active nowcast alerts stripped from response
    assert len(resp["alerts"]) == 0

    # 4. Sources cited must contain AWS ground truth sensors
    source_names = [s["source"] for s in resp.get("sources", [])]
    assert any("Ground-Truth Sensors (AWS)" in s for s in source_names)


# ------------------------------------------------------------------
# 3. FORWARD QUERY RETAINS NOWCAST / RADAR ROUTING
# ------------------------------------------------------------------
def test_forward_query_retains_nowcast():
    """Verify that forward query 'in 15 minutes' still triggers forward nowcast without past ground-truth hijacking."""
    brain = WeatherGPTBrain()
    now = datetime.now()

    future_rain_intervals = [
        Minutely15Forecast(timestamp=now + timedelta(minutes=15), precipitation=3.5, weather_code=61, rain=3.5),
    ]
    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=31.0, humidity=70, wind_speed=12.0, precipitation=0.0),
        minutely_15=future_rain_intervals,
    )
    loc = Location(latitude=19.0760, longitude=72.8777, city="Mumbai")
    req = ChatRequest(query="Will it rain in 15 minutes in Mumbai?")

    resp = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[])
    reply = resp["bot_reply"]

    # Must predict rain in approximately 15 minutes
    assert "15 minutes" in reply or "rain" in reply.lower()
    source_names = [s["source"] for s in resp.get("sources", [])]
    assert any("Minutely Model" in s or "Radar" in s for s in source_names)
