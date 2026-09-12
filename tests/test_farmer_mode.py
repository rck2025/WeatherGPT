"""Unit and integration tests for Agro-Tactical Farmer Mode (Krishi Scientist & GKMS SOP)."""

import pytest
from datetime import datetime
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
    build_agromet_scientist_briefing,
)


def get_mock_farmer_weather(soil_moisture=0.366, wind_speed_kmh=11.5, humidity=78.0, weather_code=0):
    return WeatherResponse(
        current=CurrentWeatherData(
            temperature=28.5,
            feels_like=31.0,
            humidity=humidity,
            precipitation=0.0,
            wind_speed=wind_speed_kmh,
            weather_code=weather_code,
            visibility=10000.0,
            soil_moisture_0_to_7cm=soil_moisture,
        ),
        daily=[
            DailyForecast(
                date=datetime.now(),
                temperature_max=34.0,
                temperature_min=24.0,
                precipitation=0.0,
                weather_code=0,
            ),
        ],
    )


def test_farmer_schema_contract():
    """Verify backend schema updates for ChatRequest mode='farmer' and soil_moisture_0_to_7cm."""
    # 1. ChatRequest accepts mode='farmer'
    req = ChatRequest(query="Should I irrigate today?", mode="farmer")
    assert req.mode == "farmer"

    # 2. CurrentWeatherData includes soil_moisture_0_to_7cm
    weather = CurrentWeatherData(
        temperature=27.5,
        humidity=72.0,
        soil_moisture_0_to_7cm=0.366,
    )
    assert weather.soil_moisture_0_to_7cm == 0.366


def test_agromet_scientist_briefing_builder_dry():
    """Test Agromet briefing generator under dry, favorable spraying conditions."""
    loc = Location(city="Varanasi", latitude=25.31, longitude=82.97)
    briefing = build_agromet_scientist_briefing(
        location=loc,
        temp_c=28.0,
        humidity=70.0,
        wind_spd=10.0,
        soil_vwc=0.345,
        weather_code=0,
        rain_expected=False,
    )
    assert "KRISHI AGROMET ADVISORY" in briefing
    assert "IMD GKMS SOP" in briefing
    assert "ICAR PROTOCOL" in briefing
    assert "34.5% VWC" in briefing
    assert "VARANASI" in briefing
    assert "SAFE (< 15 km/h)" in briefing
    assert "18.0 GDD" in briefing
    assert "FIELD MANAGEMENT DIRECTIVES" in briefing


def test_agromet_scientist_briefing_builder_rain_threat():
    """Test Agromet briefing generator when rain/squall is expected (critical crop-saving advice)."""
    loc = Location(city="Burdwan", latitude=23.23, longitude=87.86)
    briefing = build_agromet_scientist_briefing(
        location=loc,
        temp_c=30.0,
        humidity=88.0,
        wind_spd=22.0,
        soil_vwc=0.420,
        weather_code=95,
        rain_expected=True,
    )
    assert "CRITICAL CROP-SAVING INTERVENTIONS" in briefing
    assert "Open sluice gates" in briefing
    assert "Postpone fertilizer application" in briefing
    assert "UNFAVORABLE (Wind Drift / Rain Risk)" in briefing


def test_krishi_scientist_rag_mode_routing():
    """Test that WeatherGPTBrain routes mode='farmer' to Krishi Scientist template and sources."""
    brain = WeatherGPTBrain(db_path=":memory:", llm_model="test-mock")
    loc = Location(city="Ludhiana", latitude=30.90, longitude=75.85)
    weather = get_mock_farmer_weather()

    req = ChatRequest(query="Should I irrigate today?", mode="farmer")

    # Mock the LLM call to return a realistic Krishi Scientist reply
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = (
        "KRISHI AGROMET ADVISORY [IMD GKMS SOP]:\n"
        "1. Soil Water Content is at 36.6% VWC near field capacity. Irrigation is not recommended today.\n"
        "2. Foliar spraying window is optimal with surface wind at 11.5 km/h.\n"
        "3. Monitor for pest attack probability given 78% relative humidity."
    )
    brain.llm = mock_llm

    result = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[])
    assert "KRISHI AGROMET ADVISORY" in result["bot_reply"]

    # Check sources contain GKMS / ICAR advisory
    sources = result.get("sources", [])
    assert len(sources) > 0
    assert any("GKMS" in s.get("source", "") for s in sources)
