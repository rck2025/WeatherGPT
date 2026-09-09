"""
Tests for Task 1 to Task 5: Multi-Sensor Consensus, Lightning Detection, and Confidence Scoring.
Validates:
1. Observational Microscope get_sensor_consensus (AWS + IITM Damini Lightning).
2. Pydantic Schemas (ChatResponse confidence_score, model_disagreement; WeatherAlert lightning_active).
3. Conflict Scenario: Open-Meteo = 0.0mm vs AWS = 2.5mm -> Model disagreement, 95% rain confidence, score 0.40.
4. Source Agreement Scenario -> confidence score 0.95, disagreement False.
5. Damini Lightning Alert triggering and ticker tape update condition.
"""

import pytest
from datetime import datetime

from backend.schemas import ChatRequest, ChatResponse, WeatherAlert, Location, WeatherResponse, CurrentWeatherData
from backend.services.weather.observational import (
    get_sensor_consensus,
    get_damini_lightning_feed,
    haversine_distance,
    IMD_AWS_STATIONS,
)
from backend.services.rag.service import WeatherGPTBrain


def test_haversine_distance_calculation():
    # Distance between Alipore (22.53, 88.33) and Dum Dum (22.65, 88.45) is ~18-20 km
    d = haversine_distance(22.53, 88.33, 22.65, 88.45)
    assert 15.0 < d < 22.0


def test_nearest_aws_station_resolution():
    # Query near Kolkata center (22.57, 88.36)
    consensus = get_sensor_consensus(22.57, 88.36)
    assert "Alipore" in consensus["station_name"] or "Dum Dum" in consensus["station_name"]
    assert consensus["station_distance_km"] < 15.0
    assert "source_aws" in consensus
    assert "source_lightning" in consensus


def test_sensor_consensus_aws_rain_trigger():
    # When AWS station within 10km reports >0.5mm rain in last 10m:
    # PRECIPITATION_PROBABILITY must be 95% (0.95)
    consensus = get_sensor_consensus(
        22.53, 88.33,
        mock_aws_rain=1.8,
        mock_distance_km=4.0,
    )
    assert consensus["consensus_triggered"] is True
    assert consensus["precipitation_probability"] == 0.95
    assert consensus["status"] == "CONSENSUS_RAIN_CONFIRMED"
    assert "1.8mm rain" in consensus["detail"]


def test_sensor_consensus_lightning_trigger():
    # When >3 lightning strikes are detected within 50km:
    # PRECIPITATION_PROBABILITY must be 95% (0.95)
    consensus = get_sensor_consensus(
        22.53, 88.33,
        mock_aws_rain=0.0,
        mock_lightning_strikes=6,
    )
    assert consensus["consensus_triggered"] is True
    assert consensus["precipitation_probability"] == 0.95
    assert consensus["lightning_active"] is True
    assert consensus["lightning_strikes_50km"] == 6


def test_sensor_consensus_dry_nominal():
    consensus = get_sensor_consensus(
        22.53, 88.33,
        mock_aws_rain=0.0,
        mock_lightning_strikes=0,
    )
    assert consensus["consensus_triggered"] is False
    assert consensus["precipitation_probability"] <= 0.15
    assert consensus["status"] == "NOMINAL_NO_ACTIVE_OVERRIDE"


def test_damini_lightning_feed_detection():
    feed = get_damini_lightning_feed(22.53, 88.33, radius_km=50.0, mock_strikes=4)
    assert feed["source"] == "IITM Damini Lightning Network"
    assert feed["strikes_detected"] == 4
    assert feed["lightning_active"] is True
    assert feed["warning_triggered"] is True


def test_schemas_new_fields():
    alert = WeatherAlert(
        title="Lightning Storm Warning",
        description="Active lightning cells in vicinity",
        severity="High",
        source="IITM Damini",
        lightning_active=True,
    )
    assert alert.lightning_active is True

    resp = ChatResponse(
        bot_reply="Probabilistic forecast testing",
        confidence_score=0.40,
        model_disagreement=True,
    )
    assert resp.confidence_score == 0.40
    assert resp.model_disagreement is True


def test_conflict_scenario_open_meteo_zero_vs_aws_rain():
    """
    Validation Test from Prompt:
    Action: Tell the code (mock) that Open-Meteo = 0.0mm but AWS_Station_Kolkata = 2.5mm.
    Query: 'Is it raining?'
    Target Response: 'Numerical models indicate dry weather, however, the Automatic Weather Station at Alipore (Kolkata) is reporting 2.5mm of rain. High confidence (95%) that rain is active in your sector.'
    """
    brain = WeatherGPTBrain()
    brain.mock_aws_rain = 2.5
    brain.mock_station_name = "Alipore (Kolkata)"

    # Open-Meteo predicts 0.0mm dry
    dry_weather = WeatherResponse(
        current=CurrentWeatherData(
            temperature=31.0,
            humidity=85.0,
            precipitation=0.0,
            wind_speed=12.0,
        )
    )
    req = ChatRequest(query="Is it raining?", language="en")
    loc = Location(city="Kolkata", latitude=22.53, longitude=88.33)

    result = brain.query_with_schemas(req, weather_data=dry_weather, location=loc, alerts=[])

    # Assertions
    assert result["model_disagreement"] is True
    assert result["confidence_score"] == 0.40  # Conflicts -> score is 0.40
    reply = result["bot_reply"]
    assert "numerical models indicate dry weather" in reply.lower()
    assert "automatic weather station at alipore (kolkata) is reporting 2.5mm of rain" in reply.lower()
    assert "95%" in reply


def test_consensus_agreement_scenario_sources_aligned():
    """
    When sources agree (both dry):
    model_disagreement is False, confidence_score is 0.95.
    """
    brain = WeatherGPTBrain()
    brain.mock_aws_rain = 0.0
    brain.mock_lightning_strikes = 0

    dry_weather = WeatherResponse(
        current=CurrentWeatherData(
            temperature=29.0,
            humidity=55.0,
            precipitation=0.0,
            wind_speed=8.0,
        )
    )
    req = ChatRequest(query="Is it raining?", language="en")
    loc = Location(city="Kolkata", latitude=22.53, longitude=88.33)

    result = brain.query_with_schemas(req, weather_data=dry_weather, location=loc, alerts=[])

    assert result["model_disagreement"] is False
    assert result["confidence_score"] == 0.95


def test_lightning_active_injects_weather_alert():
    """
    When lightning strikes are active, an alert with lightning_active=True is added.
    """
    brain = WeatherGPTBrain()
    brain.mock_aws_rain = 0.0
    brain.mock_lightning_strikes = 5

    weather = WeatherResponse(
        current=CurrentWeatherData(
            temperature=30.0,
            precipitation=0.0,
        )
    )
    req = ChatRequest(query="What is the weather situation?", language="en")
    loc = Location(city="Kolkata", latitude=22.53, longitude=88.33)

    result = brain.query_with_schemas(req, weather_data=weather, location=loc, alerts=[])

    alerts = result.get("alerts", [])
    lightning_alerts = [a for a in alerts if getattr(a, "lightning_active", False)]
    assert len(lightning_alerts) >= 1
    assert "Lightning" in lightning_alerts[0].title
    assert lightning_alerts[0].source == "IITM Damini Lightning Network"


def test_frontend_files_contain_task4_and_task5_requirements():
    """Verify frontend code contains required confidence gauge and lightning ticker strings."""
    with open("frontend/app.js", "r", encoding="utf-8") as f:
        app_code = f.read()

    # Task 4: Terminal gauge bar and model disagreement check
    assert "confidence-gauge-bar" in app_code
    assert "confidence_score" in app_code
    assert "model_disagreement" in app_code
    assert "is-conflict" in app_code

    # Task 5: Lightning ticker update
    assert "🚨 TACTICAL UPDATE: LIGHTNING STRIKES DETECTED WITHIN 20KM RADIUS. SEEK SHELTER." in app_code
    assert "ticker-track-lightning" in app_code

    with open("frontend/style.css", "r", encoding="utf-8") as f:
        css_code = f.read()

    assert ".confidence-gauge-bar" in css_code
    assert ".confidence-gauge-bar.is-conflict" in css_code
    assert ".ticker-track-lightning" in css_code
