"""Unit and integration tests for Aviation Mode Toggle (Tactical Flight Briefing & ATC Persona)."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    DailyForecast,
    Location,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.service import (
    WeatherGPTBrain,
    build_atc_flight_briefing,
    determine_flight_rules,
)


def get_mock_aviation_weather(visibility_m=10000.0, wind_speed_kmh=24.0, weather_code=0):
    return WeatherResponse(
        current=CurrentWeatherData(
            temperature=28.5,
            humidity=65.0,
            precipitation=0.0,
            wind_speed=wind_speed_kmh,
            weather_code=weather_code,
            visibility=visibility_m,
        ),
        daily=[
            DailyForecast(
                date=datetime.now(),
                temperature_max=32.0,
                temperature_min=24.0,
                precipitation=0.0,
            ),
        ],
    )


def test_aviation_schema_contract():
    """Verify backend schema updates for ChatRequest mode and CurrentWeatherData visibility."""
    # 1. Default mode is standard
    req_default = ChatRequest(query="Weather report")
    assert hasattr(req_default, "mode")
    assert req_default.mode == "standard"

    # 2. Can be set to aviation
    req_aviation = ChatRequest(query="Is it safe to fly?", mode="aviation")
    assert req_aviation.mode == "aviation"

    # 3. CurrentWeatherData visibility field
    current_weather = CurrentWeatherData(
        temperature=25.0,
        humidity=70.0,
        precipitation=0.0,
        wind_speed=15.0,
        visibility=8500.0,
    )
    assert current_weather.visibility == 8500.0


def test_flight_rules_determination():
    """Test VFR, MVFR, and IFR categorization based on visibility and weather codes."""
    # High visibility, clear sky -> VFR
    assert determine_flight_rules(vis_km=10.0, weather_code=0) == "VFR"
    assert determine_flight_rules(vis_km=6.0, weather_code=1) == "VFR"

    # Marginal visibility (3.0 - 4.9 km) -> MVFR
    assert determine_flight_rules(vis_km=4.0, weather_code=2) == "MVFR"
    assert determine_flight_rules(vis_km=3.5, weather_code=3) == "MVFR"

    # Low visibility (< 3.0 km) -> IFR
    assert determine_flight_rules(vis_km=2.0, weather_code=2) == "IFR"
    assert determine_flight_rules(vis_km=0.8, weather_code=45) == "IFR"

    # Thunderstorm (code 95, 96, 99) forces IFR regardless of visibility
    assert determine_flight_rules(vis_km=10.0, weather_code=95) == "IFR"


def test_atc_briefing_builder():
    """Test tactical METAR/ATC briefing generator."""
    loc = Location(city="Kolkata", latitude=22.57, longitude=88.36)
    briefing = build_atc_flight_briefing(
        location=loc,
        vis_km=10.0,
        vis_nm=5.4,
        wind_kt=12.0,
        category="VFR",
        weather_code=0,
        ceiling_desc="Unlimited ceiling (> 10,000 ft AGL)",
        hazards=[],
    )
    assert "METAR REPORT" in briefing
    assert "VFR" in briefing
    assert "10.0 KM" in briefing or "10.0 km" in briefing.lower()
    assert "5.4 NM" in briefing
    assert "KOLKATA" in briefing.upper()


def test_aviation_mode_atc_persona_hard_lock():
    """Verify that mode='aviation' triggers the ATC Persona even on simple, casual queries."""
    brain = WeatherGPTBrain()
    weather = get_mock_aviation_weather(visibility_m=10000.0, wind_speed_kmh=20.0)
    loc = Location(city="Kolkata", latitude=22.57, longitude=88.36)

    # Even a casual query like "How's the day?" must get ATC / METAR briefing in aviation mode
    req = ChatRequest(query="How's the day?", mode="aviation")
    res = brain.query_with_schemas(req, weather_data=weather, location=loc, alerts=[])

    bot_reply = res["bot_reply"]
    # Check for ATC/METAR terminology
    assert any(term in bot_reply.upper() for term in ["METAR", "VFR", "IFR", "ATC", "FLIGHT", "VISIBILITY"])
    assert "KM" in bot_reply.upper() or "NM" in bot_reply.upper()


def test_standard_mode_preserves_conversational_persona():
    """Verify that mode='standard' retains standard friendly/conversational responses for greetings."""
    brain = WeatherGPTBrain()
    weather = get_mock_aviation_weather()
    loc = Location(city="Kolkata", latitude=22.57, longitude=88.36)

    req = ChatRequest(query="Hi!", mode="standard")
    res = brain.query_with_schemas(req, weather_data=weather, location=loc, alerts=[])

    bot_reply = res["bot_reply"]
    # Small talk greeting in standard mode
    assert "hello" in bot_reply.lower() or "weathergpt" in bot_reply.lower()
    # Should not force a full METAR report for 'Hi!' in standard mode
    assert "METAR REPORT:" not in bot_reply


def test_aviation_mode_convective_hazard_warning():
    """Verify convective hazards (thunderstorm/wind shear) are flagged in Aviation Mode."""
    brain = WeatherGPTBrain()
    # Thunderstorm weather code 95
    weather = get_mock_aviation_weather(visibility_m=4000.0, wind_speed_kmh=55.0, weather_code=95)
    loc = Location(city="Mumbai", latitude=19.07, longitude=72.87)

    req = ChatRequest(query="Is it safe to fly to Mumbai right now?", mode="aviation")
    res = brain.query_with_schemas(req, weather_data=weather, location=loc, alerts=[])

    bot_reply = res["bot_reply"]
    assert any(term in bot_reply.upper() for term in ["IFR", "THUNDERSTORM", "CONVECTIVE", "HAZARD", "WARNING"])
