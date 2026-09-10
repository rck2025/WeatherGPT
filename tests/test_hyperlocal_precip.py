"""
Unit Test Suite for Hyperlocal Precipitation Intelligence & Ground-Truth First Architecture.
Tests:
1. Rain Timing Engine (precip_logic.py) - start/stop/stable scans.
2. Ground-Truth First Service (observational.py) - AWS sensor > Global NWP model.
3. Intent Categorization (brain.py) - PRECIP_QUERY_YESNO and PRECIP_QUERY_DURATION in English and Indic languages.
4. Direct Response Brain & Prompt Injection (service.py) - Direct 1-sentence answers, no temperature/wind clutter, lagging model apology.
"""

from datetime import datetime, timedelta
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    DailyForecast,
    Location,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.weather.precip_logic import analyze_precip_timing
from backend.services.weather.observational import get_hyperlocal_status
from backend.services.rag.brain import (
    detect_precip_intent,
    PRECIP_QUERY_YESNO,
    PRECIP_QUERY_DURATION,
)
from backend.services.rag.service import WeatherGPTBrain


# =====================================================================
# 1. Rain Timing Engine Tests
# =====================================================================
def test_precip_timing_stopping():
    """Active rain now (2.5mm) stopping after 30 mins (index 2)."""
    precip_array = [2.5, 1.2, 0.0, 0.0]
    time_array = ["12:00", "12:15", "12:30", "12:45"]
    status, minutes = analyze_precip_timing(precip_array, time_array, threshold=0.1)
    assert status == "STOPPING"
    assert minutes == 30


def test_precip_timing_starting():
    """Dry now, rain starting after 45 mins (index 3)."""
    precip_array = [0.0, 0.0, 0.0, 1.8, 2.0]
    status, minutes = analyze_precip_timing(precip_array, threshold=0.1)
    assert status == "STARTING"
    assert minutes == 45


def test_precip_timing_stable_dry():
    """Continuous dry weather returns STABLE, 0."""
    precip_array = [0.0, 0.0, 0.0, 0.0]
    status, minutes = analyze_precip_timing(precip_array)
    assert status == "STABLE"
    assert minutes == 0


def test_precip_timing_stable_rain():
    """Continuous rain that does not cease within array returns STABLE, 0."""
    precip_array = [1.5, 2.0, 1.8, 1.2]
    status, minutes = analyze_precip_timing(precip_array)
    assert status == "STABLE"
    assert minutes == 0


# =====================================================================
# 2. Ground-Truth First Service Tests (Sensor > Model)
# =====================================================================
def test_hyperlocal_ground_truth_sensor_priority():
    """AWS Ground Sensor detects rain (0.5mm) while global model predicts 0.0mm dry."""
    aws_data = {"rainfall_last_10m": 0.5}
    is_raining, source = get_hyperlocal_status(22.57, 88.36, model_precip=0.0, aws_data=aws_data)
    assert is_raining is True
    assert source == "RECORDED_BY_SENSOR"


def test_hyperlocal_model_fallback_when_sensor_dry():
    """AWS Ground Sensor reports dry (0.0mm), but model predicts rain (1.4mm)."""
    aws_data = {"rainfall_last_10m": 0.0}
    is_raining, source = get_hyperlocal_status(22.57, 88.36, model_precip=1.4, aws_data=aws_data)
    assert is_raining is True
    assert source == "PREDICTED_BY_MODEL"


def test_hyperlocal_status_clear():
    """Both AWS Ground Sensor and model report dry."""
    aws_data = {"rainfall_last_10m": 0.0}
    is_raining, source = get_hyperlocal_status(22.57, 88.36, model_precip=0.0, aws_data=aws_data)
    assert is_raining is False
    assert source == "CLEAR"


# =====================================================================
# 3. Intent Categorization Tests (English & Indic)
# =====================================================================
def test_precip_intent_categorization():
    # Yes/No Queries
    assert detect_precip_intent("Is it raining?") == PRECIP_QUERY_YESNO
    assert detect_precip_intent("is it raining outside") == PRECIP_QUERY_YESNO
    assert detect_precip_intent("kya barish ho rahi hai") == PRECIP_QUERY_YESNO
    assert detect_precip_intent("বৃষ্টি কি হচ্ছে") == PRECIP_QUERY_YESNO

    # Duration Queries
    assert detect_precip_intent("When will it stop?") == PRECIP_QUERY_DURATION
    assert detect_precip_intent("when will rain stop") == PRECIP_QUERY_DURATION
    assert detect_precip_intent("baarish kab rukegi") == PRECIP_QUERY_DURATION
    assert detect_precip_intent("barish kab band hogi") == PRECIP_QUERY_DURATION
    assert detect_precip_intent("When will it start?") == PRECIP_QUERY_DURATION

    # Tomorrow / Future Multi-Day Queries must NOT be hijacked
    assert detect_precip_intent("Will it rain tomorrow in Kolkata?") is None
    assert detect_precip_intent("Kal subah barish hogi kya?") is None


# =====================================================================
# 4. Hyperlocal Brain & Prompt Injection (service.py)
# =====================================================================
def test_prompt_injection_hyperlocal_data_and_role():
    """Verify [ROLE: HYPERLOCAL METEOROLOGICAL OFFICER] and HYPERLOCAL_DATA are injected into raw prompt."""
    brain = WeatherGPTBrain()
    weather = WeatherResponse(
        current=CurrentWeatherData(
            temperature=29.0,
            humidity=80.0,
            precipitation=0.0,
            wind_speed=10.0,
        )
    )
    loc = Location(city="Kolkata", latitude=22.57, longitude=88.36)
    req = ChatRequest(query="Is it raining?")

    captured_prompts = []
    mock_llm = MagicMock()
    def mock_invoke(p):
        captured_prompts.append(p)
        resp = MagicMock()
        resp.text = "No, it is currently dry in your area."
        return resp
    mock_llm.invoke.side_effect = mock_invoke

    with patch.object(brain, "_create_llm", return_value=mock_llm), \
         patch.object(brain, "llm", mock_llm):
        result = brain.query_with_schemas(req, weather_data=weather, location=loc, alerts=[])

    assert len(captured_prompts) > 0
    raw_prompt = captured_prompts[0]

    assert "[ROLE: HYPERLOCAL METEOROLOGICAL OFFICER]" in raw_prompt
    assert "RULES:" in raw_prompt
    assert "NO GENERIC HEADERS" in raw_prompt
    assert 'LOCALITY: Use the phrase "in your area"' in raw_prompt
    assert "HYPERLOCAL_DATA:" in raw_prompt
    assert "Status: Dry, Source: GFS Model" in raw_prompt


def test_is_it_raining_direct_response_validation():
    """
    Validation Test: When asked 'Is it raining?', the bot must not mention temperature or wind speed.
    It must say 'Yes' or 'No' and reference 'your area'.
    """
    brain = WeatherGPTBrain()
    # 1. Dry weather scenario
    dry_weather = WeatherResponse(
        current=CurrentWeatherData(
            temperature=32.5,
            feels_like=38.0,
            humidity=75.0,
            precipitation=0.0,
            wind_speed=18.0,
        )
    )
    loc = Location(city="Kolkata", latitude=22.57, longitude=88.36)
    req = ChatRequest(query="Is it raining?")

    # Force fallback to test deterministic brain formatting
    with patch.object(brain, "llm", None), patch.object(brain, "_create_llm", return_value=None):
        res_dry = brain.query_with_schemas(req, weather_data=dry_weather, location=loc, alerts=[])

    reply_dry = res_dry["bot_reply"]
    # Must start with No and reference your area
    assert reply_dry.startswith("No")
    assert "in your area" in reply_dry
    # Must NOT mention temperature or wind speed
    assert "32.5" not in reply_dry
    assert "temperature" not in reply_dry.lower()
    assert "wind" not in reply_dry.lower()
    assert "km/h" not in reply_dry.lower()

    # 2. Raining scenario
    wet_weather = WeatherResponse(
        current=CurrentWeatherData(
            temperature=27.0,
            feels_like=30.0,
            humidity=92.0,
            precipitation=3.5,
            wind_speed=24.0,
        )
    )
    with patch.object(brain, "llm", None), patch.object(brain, "_create_llm", return_value=None):
        res_wet = brain.query_with_schemas(req, weather_data=wet_weather, location=loc, alerts=[])

    reply_wet = res_wet["bot_reply"]
    assert reply_wet.startswith("Yes")
    assert "in your area" in reply_wet
    assert "27.0" not in reply_wet
    assert "temperature" not in reply_wet.lower()
    assert "wind" not in reply_wet.lower()


def test_conflict_resolution_lagging_model():
    """
    Conflict Resolution: When model is 0.0mm but Ground Sensor sees rain,
    bot must apologize and state:
    'The model is lagging, but our local ground sensors detect active rain in your sector right now.'
    """
    brain = WeatherGPTBrain()
    brain.mock_aws_rain = 2.5
    dry_model_weather = WeatherResponse(
        current=CurrentWeatherData(
            temperature=30.0,
            humidity=80.0,
            precipitation=0.0,
            wind_speed=10.0,
        )
    )
    loc = Location(city="Kolkata", latitude=22.53, longitude=88.33)
    req = ChatRequest(query="Is it raining?")

    with patch.object(brain, "llm", None), patch.object(brain, "_create_llm", return_value=None):
        res_conflict = brain.query_with_schemas(req, weather_data=dry_model_weather, location=loc, alerts=[])

    reply = res_conflict["bot_reply"]
    assert "the model is lagging, but our local ground sensors detect active rain in your sector right now" in reply.lower()
    # Zero temperature or wind telemetry
    assert "temperature" not in reply.lower()
    assert "wind" not in reply.lower()
    assert res_conflict["model_disagreement"] is True
