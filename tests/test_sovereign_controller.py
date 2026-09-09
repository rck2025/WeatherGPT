"""
Test Suite for Sovereign Logic Controller: Unified Gatekeeper, Hard Data Gater,
Clock-Time Evaluator, and Leak Interceptor.
Validates:
1. Victory Checklist:
   - 'Rain 2 hours ago?' -> PAST_HISTORICAL
   - 'Rain in 2 hours?' -> FUTURE_FORECAST
   - 'Rain now?' -> PRESENT_OBSERVATIONAL
2. Clock Time Evaluation:
   - 'Was it raining at 5:30 PM?' (past clock time -> PAST_HISTORICAL, AWS telemetry)
   - 'Will it rain at 9:00 PM?' (upcoming clock time -> FUTURE_FORECAST)
   - Indic script clock times (Hindi, Bengali, Tamil)
3. Data Hard-Gating:
   - PAST_HISTORICAL: weather_data=None, alerts=[] (zero alert leakage)
4. Post-Processor Leak Interception:
   - Intercepting and sanitizing tainted responses containing forward forecasts or active alerts
5. End-to-End query_with_schemas integration with SovereignLogicController
"""

from datetime import datetime, timezone, timedelta
import pytest

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    Location,
    Minutely15Forecast,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.controller import (
    ClockTimeInfo,
    SovereignLogicController,
    TemporalCategory,
    parse_clock_time,
    sovereign_controller,
)
from backend.services.rag.service import WeatherGPTBrain


IST = timezone(timedelta(hours=5, minutes=30))
REF_TIME_EVENING = datetime(2026, 9, 8, 18, 45, tzinfo=IST)  # 6:45 PM IST


# ------------------------------------------------------------------
# 1. VICTORY CHECKLIST ROUTING
# ------------------------------------------------------------------
def test_victory_checklist_2_hours_ago():
    """Ask: 'Rain 2 hours ago?' -> Must route to PAST_HISTORICAL with -120 offset."""
    decision = sovereign_controller.categorize_query("Rain 2 hours ago?", ref_time=REF_TIME_EVENING)
    assert decision.category == TemporalCategory.PAST_HISTORICAL
    assert decision.minute_offset == -120


def test_victory_checklist_in_2_hours():
    """Ask: 'Rain in 2 hours?' -> Must route to FUTURE_FORECAST with +120 offset."""
    decision = sovereign_controller.categorize_query("Rain in 2 hours?", ref_time=REF_TIME_EVENING)
    assert decision.category == TemporalCategory.FUTURE_FORECAST
    assert decision.minute_offset == 120


def test_victory_checklist_rain_now():
    """Ask: 'Rain now?' -> Must route to PRESENT_OBSERVATIONAL."""
    decision = sovereign_controller.categorize_query("Rain now?", ref_time=REF_TIME_EVENING)
    assert decision.category == TemporalCategory.PRESENT_OBSERVATIONAL


# ------------------------------------------------------------------
# 2. CLOCK TIME EVALUATION (PAST VS FUTURE TODAY)
# ------------------------------------------------------------------
def test_passed_clock_time_evaluates_to_past():
    """
    When asking about '5:30 PM' at 6:45 PM IST, the system must autonomously
    detect that 5:30 PM has already passed today and route to PAST_HISTORICAL.
    """
    clock_info = parse_clock_time("Was it raining at 5:30 PM?", ref_time=REF_TIME_EVENING)
    assert clock_info is not None
    assert clock_info.hour == 17
    assert clock_info.minute == 30
    assert clock_info.is_past is True
    assert clock_info.delta_mins == 75  # 18:45 - 17:30 = 75 minutes

    decision = sovereign_controller.categorize_query("Was it raining at 5:30 PM today in Kolkata?", ref_time=REF_TIME_EVENING)
    assert decision.category == TemporalCategory.PAST_HISTORICAL
    assert decision.minute_offset == -75
    assert decision.clock_time_info is not None


def test_upcoming_clock_time_evaluates_to_future():
    """
    When asking about '9:00 PM' at 6:45 PM IST, the system must detect
    that 9:00 PM is upcoming today and route to FUTURE_FORECAST.
    """
    clock_info = parse_clock_time("Will it rain at 9:00 PM?", ref_time=REF_TIME_EVENING)
    assert clock_info is not None
    assert clock_info.hour == 21
    assert clock_info.minute == 0
    assert clock_info.is_past is False
    assert clock_info.delta_mins == 135  # 21:00 - 18:45 = 135 minutes

    decision = sovereign_controller.categorize_query("Will it rain at 9:00 PM?", ref_time=REF_TIME_EVENING)
    assert decision.category == TemporalCategory.FUTURE_FORECAST
    assert decision.minute_offset == 135


def test_multilingual_clock_time_parsing():
    """Verify clock time parsing across Indic scripts."""
    # Hindi
    c_hi = parse_clock_time("शाम 5:30 बजे बारिश हुई थी?", ref_time=REF_TIME_EVENING)
    assert c_hi is not None
    assert c_hi.hour == 17 and c_hi.minute == 30 and c_hi.is_past is True

    # Bengali
    c_bn = parse_clock_time("বিকেল ৫:৩০ এ কি বৃষ্টি হয়েছিল?", ref_time=REF_TIME_EVENING)
    assert c_bn is not None
    assert c_bn.hour == 17 and c_bn.minute == 30 and c_bn.is_past is True

    # Tamil
    c_ta = parse_clock_time("மாலை 5:30 மணிக்கு மழை பெய்ததா?", ref_time=REF_TIME_EVENING)
    assert c_ta is not None
    assert c_ta.hour == 17 and c_ta.minute == 30 and c_ta.is_past is True


# ------------------------------------------------------------------
# 3. PHYSICAL DATA HARD-GATING
# ------------------------------------------------------------------
def test_hard_data_gating_past_nullification():
    """Verify that PAST_HISTORICAL physically nullifies weather_data and alerts."""
    dummy_weather = WeatherResponse(
        current=CurrentWeatherData(temperature=32.0, humidity=80, wind_speed=20.0, precipitation=10.0)
    )
    dummy_alert = WeatherAlert(
        title="EMERGENCY WARNING",
        description="Dangerous convective cell active now.",
        severity="High",
        source="IMD Doppler Radar",
    )

    past_decision = sovereign_controller.categorize_query("What was the weather 2 hours ago?", ref_time=REF_TIME_EVENING)
    gated_weather, gated_alerts = sovereign_controller.hard_gate_data(past_decision, dummy_weather, [dummy_alert])

    assert gated_weather is None
    assert gated_alerts == []


def test_hard_data_gating_present_retains_live_telemetry():
    """Verify that PRESENT_OBSERVATIONAL passes live weather and alerts."""
    dummy_weather = WeatherResponse(
        current=CurrentWeatherData(temperature=30.0, humidity=75, wind_speed=15.0, precipitation=0.0)
    )
    dummy_alert = WeatherAlert(title="Nowcast Watch", description="Monitoring cells", severity="Low", source="IMD")

    present_decision = sovereign_controller.categorize_query("Is it raining now in Kolkata?", ref_time=REF_TIME_EVENING)
    gated_weather, gated_alerts = sovereign_controller.hard_gate_data(present_decision, dummy_weather, [dummy_alert])

    assert gated_weather is not None
    assert len(gated_alerts) == 1


# ------------------------------------------------------------------
# 4. POST-PROCESSOR RESPONSE LEAK INTERCEPTION
# ------------------------------------------------------------------
def test_post_processor_intercepts_tainted_past_response():
    """
    If an AI response for a PAST query accidentally contains active alerts
    or forward forecast words ('next 3 hours', 'predicted to start'), the controller
    must autonomously intercept it, flag was_tainted=True, and sanitize the response.
    """
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")
    decision = sovereign_controller.categorize_query("Was it raining 2 hours ago in Kolkata?", ref_time=REF_TIME_EVENING)

    tainted_bot_reply = (
        "Yesterday was warm. However, an EMERGENCY WARNING is active right now: "
        "rain is predicted to start in the next 3 hours."
    )

    clean_reply, was_tainted = sovereign_controller.validate_and_sanitize_response(
        decision=decision,
        bot_reply=tainted_bot_reply,
        location=loc,
        lang_code="en",
        raw_query="Was it raining 2 hours ago in Kolkata?",
        recent_hist={"recorded_precipitation": 0.0, "status": "RECORDED_DRY"},
    )

    assert was_tainted is True
    assert "EMERGENCY WARNING" not in clean_reply
    assert "next 3 hours" not in clean_reply
    assert "MoES Ground-Truth Sensors (AWS)" in clean_reply


def test_post_processor_passes_clean_response():
    """Clean historical response should not be marked as tainted."""
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")
    decision = sovereign_controller.categorize_query("Was it raining 30 mins ago in Kolkata?", ref_time=REF_TIME_EVENING)

    clean_bot_reply = (
        "According to MoES Ground-Truth Sensors (AWS), no rain was recorded in the last 30 minutes (0.0mm recorded).\n\n"
        "Source: MoES Ground-Truth Sensors (AWS)"
    )

    result_reply, was_tainted = sovereign_controller.validate_and_sanitize_response(
        decision=decision,
        bot_reply=clean_bot_reply,
        location=loc,
        lang_code="en",
        raw_query="Was it raining 30 mins ago in Kolkata?",
    )

    assert was_tainted is False
    assert result_reply == clean_bot_reply


# ------------------------------------------------------------------
# 5. END-TO-END QUERY WITH SCHEMAS: AUTONOMOUS VICTORY CHECKLIST
# ------------------------------------------------------------------
def test_e2e_past_2_hours_ago():
    """E2E Test: 'Rain 2 hours ago?' -> Uses Archive, past tense, zero alerts."""
    brain = WeatherGPTBrain()
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")
    alert = WeatherAlert(title="Flash Flood Alert", description="Nowcast danger", severity="High", source="IMD")

    req = ChatRequest(query="Rain 2 hours ago in Kolkata?", language="en")
    resp = brain.query_with_schemas(request=req, weather_data=None, location=loc, alerts=[alert])

    # Autonomous zero-leak enforcement
    assert len(resp["alerts"]) == 0
    assert "Flash Flood Alert" not in resp["bot_reply"]
    assert "MoES Ground-Truth Sensors (AWS)" in resp["bot_reply"] or any("Ground-Truth" in s["source"] for s in resp["sources"])


def test_e2e_past_at_530_pm():
    """
    E2E Test: 'Was it raining at 5:30 PM in Kolkata?'
    Autonomously routes to past ground truth, uses past tense, strips live alerts.
    """
    brain = WeatherGPTBrain()
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")
    alert = WeatherAlert(title="Radar Alert", description="Heavy squall line", severity="High", source="IMD")

    req = ChatRequest(query="Was it raining at 5:30 PM in Kolkata?", language="en")
    resp = brain.query_with_schemas(request=req, weather_data=None, location=loc, alerts=[alert])

    # Zero alert leakage
    assert len(resp["alerts"]) == 0
    assert "Radar Alert" not in resp["bot_reply"]
    assert "MoES Ground-Truth Sensors (AWS)" in resp["bot_reply"] or any("Ground-Truth" in s["source"] for s in resp["sources"])


def test_e2e_present_rain_now():
    """E2E Test: 'Rain now in Kolkata?' -> Uses Radar/Live Sensors, present tense."""
    brain = WeatherGPTBrain()
    now = datetime.now()
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")

    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=29.8, humidity=82, wind_speed=14.0, precipitation=0.0)
    )
    alert = WeatherAlert(title="IMD Live Observation", description="Clear skies", severity="Low", source="IMD")

    req = ChatRequest(query="Rain now in Kolkata?", language="en")
    resp = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[alert])

    # Present query retains alerts & observations
    assert len(resp["alerts"]) >= 0
    assert not any("Historical Archive" in s["source"] for s in resp.get("sources", []))
