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


def test_metar_decoder():
    """Verify regex parsing of raw IMD METAR telemetry into normalized dict."""
    from backend.services.weather.metar import decode_metar

    # Sample standard IMD METAR from VECC Kolkata
    raw_metar = "METAR VECC 100230Z 02008KT 4500 HZ FEW025 28/22 Q1012 NOSIG"
    decoded = decode_metar(raw_metar)

    assert decoded["wind_dir"] == "020"
    assert decoded["wind_speed_kts"] == 8
    assert decoded["visibility_m"] == 4500
    assert decoded["temp_c"] == 28
    assert decoded["dewpoint_c"] == 22
    assert decoded["qnh_hpa"] == 1012
    assert decoded["raw"] == raw_metar

    # Convective + Wind shear METAR
    severe_metar = "METAR VECC 101830Z 18038G45KT 1200 +TSRA BKN015CB 24/23 Q1006 WS RWY19L"
    decoded_severe = decode_metar(severe_metar)
    assert decoded_severe["wind_speed_kts"] == 38
    assert decoded_severe["wind_gust_kts"] == 45
    assert decoded_severe["visibility_m"] == 1200
    assert decoded_severe["wind_shear"] is True
    assert decoded_severe["wind_shear_rwy"] == "19L"
    assert decoded_severe["convective_hazard"] is True


def test_flight_rules_classification_icao_dgca():
    """Verify ICAO Annex 3 and DGCA CAR Series M decision thresholds."""
    from backend.services.weather.aviation_logic import classify_flight_rules

    # VFR: High visibility, calm winds
    vfr_badge, vfr_desc = classify_flight_rules({"visibility_m": 8000, "wind_speed_kts": 10})
    assert "VFR (SUITABLE)" in vfr_badge
    assert "Standard visual flight rules apply" in vfr_desc

    # MVFR: Visibility between 1500m and 5000m
    mvfr_badge, mvfr_desc = classify_flight_rules({"visibility_m": 3500, "wind_speed_kts": 15})
    assert "MVFR (MARGINAL)" in mvfr_badge
    assert "Reduced visibility" in mvfr_desc

    # IFR: Visibility < 1500m (LVP active)
    ifr_badge_vis, ifr_desc_vis = classify_flight_rules({"visibility_m": 1200, "wind_speed_kts": 10})
    assert "IFR ONLY (LVP ACTIVE)" in ifr_badge_vis
    assert "Low Visibility Procedures" in ifr_desc_vis

    # IFR: Wind > 35 kts
    ifr_badge_wind, _ = classify_flight_rules({"visibility_m": 9000, "wind_speed_kts": 40})
    assert "IFR ONLY (LVP ACTIVE)" in ifr_badge_wind

    # IFR: Wind shear active
    ifr_badge_ws, ifr_desc_ws = classify_flight_rules({"visibility_m": 9000, "wind_speed_kts": 15, "wind_shear": True})
    assert "IFR ONLY (LVP ACTIVE)" in ifr_badge_ws
    assert "Wind shear" in ifr_desc_ws


def test_icao_airport_resolver():
    """Verify geospatial mapping of Indian cities to international aerodrome ICAO codes."""
    from backend.services.location.resolver import get_nearest_icao

    # Exact city matches
    icao_kol, name_kol = get_nearest_icao(22.57, 88.36, "Kolkata")
    assert icao_kol == "VECC"
    assert "KOLKATA" in name_kol.upper()

    icao_del, name_del = get_nearest_icao(28.61, 77.20, "Delhi")
    assert icao_del == "VIDP"
    assert "DELHI" in name_del.upper()

    icao_mum, name_mum = get_nearest_icao(19.07, 72.87, "Mumbai")
    assert icao_mum == "VABB"
    assert "MUMBAI" in name_mum.upper()

    # Coordinate proximity fallback (near Delhi coordinates)
    icao_del_coord, _ = get_nearest_icao(28.55, 77.09)
    assert icao_del_coord == "VIDP"


def test_mwo_kolkata_prioritization():
    """Verify that VECC lock triggers MWO Kolkata live HTML prioritization and source tagging."""
    brain = WeatherGPTBrain()
    weather = get_mock_aviation_weather(visibility_m=6000.0, wind_speed_kmh=15.0)
    loc = Location(city="Kolkata", latitude=22.65, longitude=88.45)

    req = ChatRequest(query="Provide aviation flight briefing for VECC", mode="aviation")
    res = brain.query_with_schemas(req, weather_data=weather, location=loc, alerts=[])

    assert res.get("icao_code") == "VECC"
    assert res.get("metar_raw") is not None
    assert "VECC" in res["metar_raw"]

    # Verify MWO Kolkata prioritized source
    sources = res.get("sources", [])
    assert any("MWO" in s.get("source", "") or "VECC" in s.get("source", "") for s in sources)

