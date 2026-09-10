"""Tests for Conversational Brain Refactor: Multi-Turn Memory & Adaptive Persona."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

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
    extract_city_from_text,
    is_small_talk,
    is_vague_weather_query,
)


def get_mock_weather():
    return WeatherResponse(
        current=CurrentWeatherData(
            temperature=31.0,
            humidity=60.0,
            precipitation=0.0,
            wind_speed=12.0,
        ),
        daily=[
            DailyForecast(
                date=datetime.now(),
                temperature_max=32.0,
                temperature_min=24.0,
                precipitation=0.0,
            ),
            DailyForecast(
                date=datetime.now() + timedelta(days=1),
                temperature_max=33.5,
                temperature_min=25.0,
                precipitation=0.0,
            ),
        ],
    )


def test_chat_request_history_contract():
    """Step 1 validation: ChatRequest schema has history field default to empty list."""
    req_default = ChatRequest(query="Weather today?")
    assert hasattr(req_default, "history")
    assert req_default.history == []

    req_with_history = ChatRequest(
        query="Is it safe there tomorrow?",
        history=[
            {"role": "user", "content": "Weather in Delhi?"},
            {"role": "assistant", "content": "Delhi is currently 31°C and clear."},
        ],
    )
    assert len(req_with_history.history) == 2
    assert req_with_history.history[0]["role"] == "user"
    assert req_with_history.history[1]["role"] == "assistant"


def test_small_talk_and_pleasantries():
    """Task 2.1 validation: 'Hi' and 'Thanks' respond warmly & concisely without full weather report."""
    brain = WeatherGPTBrain()
    weather = get_mock_weather()
    loc = Location(city="Kolkata", latitude=22.57, longitude=88.36)

    # 1. Greeting
    req_hi = ChatRequest(query="Hi!")
    res_hi = brain.query_with_schemas(req_hi, weather_data=weather, location=loc, alerts=[])
    assert "hello" in res_hi["bot_reply"].lower() or "weathergpt" in res_hi["bot_reply"].lower()
    # Ensure no massive weather data dump
    assert "surface telemetry:" not in res_hi["bot_reply"].lower()

    # 2. Gratitude
    req_thanks = ChatRequest(query="Thank you so much!")
    res_thanks = brain.query_with_schemas(req_thanks, weather_data=weather, location=loc, alerts=[])
    assert "welcome" in res_thanks["bot_reply"].lower()


def test_ambiguity_handling_stops_and_asks_clarification():
    """Task 2.2 validation: Vague questions without location prompt for clarification."""
    brain = WeatherGPTBrain()
    weather = get_mock_weather()

    # When location is unspecified or default
    vague_req = ChatRequest(query="Will it rain?", history=[])
    res = brain.query_with_schemas(vague_req, weather_data=weather, location=None, alerts=[])

    assert "which city" in res["bot_reply"].lower() or "specify your location" in res["bot_reply"].lower()


def test_proactive_safety_interjection_on_red_alert():
    """Task 3 validation: RED ALERT or lightning triggers proactive safety interjection."""
    brain = WeatherGPTBrain()
    weather = get_mock_weather()
    loc = Location(city="Kolkata", latitude=22.57, longitude=88.36)

    critical_alert = WeatherAlert(
        title="Red Alert: Severe Supercyclonic Storm Approaching",
        description="Red Alert issued: Wind speeds exceeding 120 km/h with torrential rain.",
        severity="Critical",
        source="IMD Cyclone Warning Centre",
        latitude=22.57,
        longitude=88.36,
    )

    # Even on small talk, the AI must proactively interject
    req_chat = ChatRequest(query="Hello there!")
    res = brain.query_with_schemas(req_chat, weather_data=weather, location=loc, alerts=[critical_alert])

    reply_lower = res["bot_reply"].lower()
    assert "approaching your sector" in reply_lower or "before we continue" in reply_lower
    assert "severe storm" in reply_lower or "alert" in reply_lower


def test_reference_resolution_and_multi_turn_history():
    """Task 1 & 4 validation: Pronoun 'there' resolves to Delhi from previous turn."""
    brain = WeatherGPTBrain()
    weather = get_mock_weather()
    delhi_loc = Location(city="Delhi", latitude=28.6139, longitude=77.2090)

    # Turn 2 query with history
    turn2_req = ChatRequest(
        query="Is it safe there tomorrow?",
        history=[
            {"role": "user", "content": "Weather in Delhi?"},
            {"role": "assistant", "content": "Current weather in Delhi: 31°C with clear skies and calm winds."},
        ],
    )

    captured_prompts = []
    mock_llm = MagicMock()
    def mock_invoke(p):
        captured_prompts.append(p)
        resp = MagicMock()
        resp.text = "Tomorrow in Delhi, conditions are safe with a maximum temperature of 33.5°C and no severe precipitation expected. (SOURCE: Open-Meteo)"
        return resp
    mock_llm.invoke.side_effect = mock_invoke

    with patch.object(brain, "_create_llm", return_value=mock_llm), \
         patch.object(brain, "llm", mock_llm):
        result = brain.query_with_schemas(turn2_req, weather_data=weather, location=delhi_loc, alerts=[])

    assert len(captured_prompts) > 0
    raw_prompt = captured_prompts[0]

    # Verify conversation history was passed to Gemini
    assert "CONVERSATION_HISTORY" in raw_prompt
    assert "Weather in Delhi?" in raw_prompt
    assert "Current weather in Delhi" in raw_prompt
    assert "USER_QUESTION: Is it safe there tomorrow?" in raw_prompt
    assert "TASK 1: MULTI-TURN MEMORY INTEGRATION & PRONOUN RESOLUTION" in raw_prompt

    # Verify response
    assert "delhi" in result["bot_reply"].lower()


def test_chat_endpoint_multi_turn_continuity():
    """Grand Finale Validation: End-to-end multi-turn conversational test over /chat."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # Turn 1: Small talk greeting
    res1 = client.post("/chat", json={"query": "Hi!"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert "hello" in data1["bot_reply"].lower() or "weathergpt" in data1["bot_reply"].lower()

    # Turn 2: Ask about Delhi
    res2 = client.post("/chat", json={
        "query": "Weather in Delhi?",
        "history": [
            {"role": "user", "content": "Hi!"},
            {"role": "assistant", "content": data1["bot_reply"]},
        ],
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["location"]["city"].lower() == "delhi"
    assert "delhi" in data2["bot_reply"].lower()

    # Turn 3: Multi-turn reference resolution - 'Is it safe there tomorrow?'
    res3 = client.post("/chat", json={
        "query": "Is it safe there tomorrow?",
        "history": [
            {"role": "user", "content": "Weather in Delhi?"},
            {"role": "assistant", "content": data2["bot_reply"]},
        ],
    })
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["location"]["city"].lower() == "delhi"
    assert "delhi" in data3["bot_reply"].lower() or "tomorrow" in data3["bot_reply"].lower()
