"""
Unit Test Suite for Intent-First RAG & Temporal Filtering (backend/services/rag/service.py)

Tests:
1. Temporal Intent Detection (future vs safety vs current)
2. Prompt Ingestion Verification (USER_QUESTION literal injection, FORECAST_DATA, LIVE_TELEMETRY, IMD_BULLETINS)
3. Exclusion of 3-Hour Nowcast from Tomorrow context
4. Intent-First Grounded Fallback (Answers Tomorrow's question with tomorrow's metrics, not today's nowcast)
"""
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    DailyForecast,
    Location,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.service import WeatherGPTBrain, detect_temporal_intent


def get_mock_weather_data():
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    return WeatherResponse(
        current=CurrentWeatherData(
            temperature=31.2,
            feels_like=36.4,
            humidity=78.0,
            precipitation=0.0,
            wind_speed=14.5,
            weather_code=1,
        ),
        daily=[
            DailyForecast(
                date=today,
                temperature_max=32.0,
                temperature_min=26.0,
                precipitation=1.0,
                weather_code=2,
            ),
            DailyForecast(
                date=tomorrow,
                temperature_max=34.5,
                temperature_min=27.2,
                precipitation=4.2,
                weather_code=61,
            ),
            DailyForecast(
                date=day_after,
                temperature_max=33.0,
                temperature_min=26.5,
                precipitation=0.5,
                weather_code=3,
            ),
        ],
    )


def get_mock_active_alerts():
    return [
        WeatherAlert(
            title="IMD 3-Hour Nowcast: Severe Thunderstorm & Squall Warning",
            description="Urgent 3-hour nowcast: Moderate to intense thunderstorm with lightning, squall wind speed reaching 45-55 km/h, and intense rainfall spells likely over Kolkata in the next 3 hours.",
            severity="High",
            source="IMD",
            latitude=22.5726,
            longitude=88.3639,
        )
    ]


def test_temporal_intent_classification():
    print("\n--- [TEST 1] Temporal Intent Classification ---")
    future_queries = [
        "What is the weather tomorrow in Kolkata?",
        "Will it rain tomorrow?",
        "Tell me the 7-day forecast for Mumbai",
        "Weather outlook for next day in Delhi",
        "kal ka mausam kaisa rahega?",
    ]
    for q in future_queries:
        intent = detect_temporal_intent(q)
        print(f"  [OK] '{q}' -> Intent: {intent}")
        assert intent == "future", f"Expected 'future' for '{q}', got '{intent}'"

    safety_queries = [
        "Is it safe to go out in Kolkata right now?",
        "Can I go outside today?",
        "What safety precautions should I take for the cyclone?",
        "Should we evacuate or seek shelter?",
    ]
    for q in safety_queries:
        intent = detect_temporal_intent(q)
        print(f"  [OK] '{q}' -> Intent: {intent}")
        assert intent == "safety", f"Expected 'safety' for '{q}', got '{intent}'"

    current_queries = [
        "What is the current temperature in Delhi?",
        "How is the weather right now in Bengaluru?",
    ]
    for q in current_queries:
        intent = detect_temporal_intent(q)
        print(f"  [OK] '{q}' -> Intent: {intent}")
        assert intent == "current", f"Expected 'current' for '{q}', got '{intent}'"

    print("PASS: Temporal Intent Detection correctly identifies query intent.")


def test_prompt_injection_and_temporal_filtering_tomorrow():
    print("\n--- [TEST 2] Tomorrow Query: Intent-First Prompt & Temporal Filtering ---")
    brain = WeatherGPTBrain()
    weather = get_mock_weather_data()
    alerts = get_mock_active_alerts()
    loc = Location(city="Kolkata", state="West Bengal", country="India", latitude=22.5726, longitude=88.3639)
    req = ChatRequest(query="What is the weather tomorrow in Kolkata?", channel="text")

    captured_prompts = []

    # Mock candidate LLM to capture raw prompt passed to invoke()
    mock_llm = MagicMock()
    def mock_invoke(p):
        captured_prompts.append(p)
        # Return mock model response answering tomorrow's question
        mock_resp = MagicMock()
        mock_resp.text = "Tomorrow in Kolkata, expect a maximum temperature of 34.5°C and a minimum of 27.2°C with light rain (4.2mm). (SOURCE: Open-Meteo)"
        return mock_resp
    mock_llm.invoke.side_effect = mock_invoke

    with patch.object(brain, "_create_llm", return_value=mock_llm), \
         patch.object(brain, "llm", mock_llm):
        result = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=alerts)

    assert len(captured_prompts) > 0, "No prompt was passed to LLM invoke!"
    raw_prompt = captured_prompts[0]

    print("\n========== RAW PROMPT SENT TO LLM (TOMORROW QUERY) ==========")
    print(raw_prompt)
    print("============================================================\n")

    # Assertions on prompt structure
    assert "CRITICAL RULE: You must answer the specific USER_QUESTION provided below." in raw_prompt
    assert "USER_QUESTION: What is the weather tomorrow in Kolkata?" in raw_prompt, "Query text was not injected!"
    assert "2. FORECAST_DATA:" in raw_prompt
    assert "TOMORROW" in raw_prompt, "TOMORROW label missing in forecast data!"
    assert "34.5°C" in raw_prompt, "Tomorrow's max temperature missing from forecast data!"

    # Verify that today's 3-hour nowcast is marked as valid for today only, not tomorrow
    assert "[NOTE: Valid for TODAY only, not tomorrow]" in raw_prompt or "(Note: Applies today only)" in raw_prompt

    # Verify LLM response
    print(f"  [OK] Bot Reply: {result['bot_reply']}")
    assert "34.5°C" in result["bot_reply"]
    print("PASS: Tomorrow query cleanly prioritized FORECAST_DATA and injected user query.")


def test_intent_first_grounded_fallback():
    print("\n--- [TEST 3] Intent-First Grounded Fallback (Offline / Quota Exceeded) ---")
    brain = WeatherGPTBrain()
    weather = get_mock_weather_data()
    alerts = get_mock_active_alerts()
    loc = Location(city="Kolkata", state="West Bengal", country="India", latitude=22.5726, longitude=88.3639)

    # 1. Tomorrow Fallback Test
    req_tomorrow = ChatRequest(query="Will it rain tomorrow in Kolkata?", channel="text")
    # Force dual-model failure to trigger grounded fallback
    with patch.object(brain, "_create_llm", return_value=None), \
         patch.object(brain, "llm", None):
        res_tomorrow = brain.query_with_schemas(request=req_tomorrow, weather_data=weather, location=loc, alerts=alerts)

    print(f"  Tomorrow Fallback Response:\n  {res_tomorrow['bot_reply']}\n")
    assert "FORECAST FOR TOMORROW" in res_tomorrow["bot_reply"], "Fallback should lead with tomorrow's forecast!"
    assert "34.5°C" in res_tomorrow["bot_reply"], "Tomorrow's temperature missing in fallback!"
    # Today's nowcast must only be present as a footer note, NOT as the main answer
    assert res_tomorrow["bot_reply"].startswith("FORECAST FOR TOMORROW"), "Fallback must not lead with URGENT NOWCAST!"
    assert "Active Today Only" in res_tomorrow["bot_reply"]

    # 2. Safety Fallback Test
    req_safety = ChatRequest(query="Is it safe to go out in Kolkata?", channel="text")
    with patch.object(brain, "_create_llm", return_value=None), \
         patch.object(brain, "llm", None):
        res_safety = brain.query_with_schemas(request=req_safety, weather_data=weather, location=loc, alerts=alerts)

    print(f"  Safety Fallback Response:\n  {res_safety['bot_reply']}\n")
    assert "SAFETY ADVISORY" in res_safety["bot_reply"], "Fallback should lead with safety advisory!"
    assert "NDMP" in res_safety["bot_reply"]

    print("PASS: Grounded Fallback strictly follows Intent-First protocol instead of static nowcast override.")


def run_all():
    print("=" * 65)
    print("RUNNING INTENT-FIRST RAG & TEMPORAL FILTERING TEST SUITE")
    print("=" * 65)
    test_temporal_intent_classification()
    test_prompt_injection_and_temporal_filtering_tomorrow()
    test_intent_first_grounded_fallback()
    print("\n" + "=" * 65)
    print("ALL INTENT-FIRST RAG TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    run_all()
