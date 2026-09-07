"""Comprehensive Test Suite for Historical Climate Archive & Meteorological Depth."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta
import httpx

from backend.schemas import ChatRequest, Location, WeatherAlert, WeatherResponse
from backend.services.rag.brain import extract_target_date, WeatherGPTBrain
from backend.services.rag.service import detect_temporal_intent
from backend.services.weather.history import fetch_historical_data, HistoricalWeatherRecord


def test_extract_target_date_patterns():
    """Verify natural language date extraction across explicit, relative, and historical patterns."""
    ref = datetime(2026, 9, 6)

    # Explicit dates
    assert extract_target_date("What was the weather on August 15, 2024?", ref) == "2024-08-15"
    assert extract_target_date("Weather for 1st January 2020", ref) == "2020-01-01"
    assert extract_target_date("What was the weather on September 4th?", ref) == "2026-09-04"
    assert extract_target_date("Rainfall on 4th September", ref) == "2026-09-04"
    assert extract_target_date("How much did it rain in Kolkata on June 10, 2024?", ref) == "2024-06-10"
    assert extract_target_date("What was the weather in Odisha during Cyclone Amphan (May 20, 2020)?", ref) == "2020-05-20"
    assert extract_target_date("How was the weather on August 15, 1947?", ref) == "1947-08-15"
    assert extract_target_date("Records for 15th August 1947 in Delhi", ref) == "1947-08-15"
    assert extract_target_date("Jan 1, 2020 temperature", ref) == "2020-01-01"
    assert extract_target_date("ISO date 2023-07-15 update", ref) == "2023-07-15"

    # Relative dates
    assert extract_target_date("August 15th last year", ref) == "2025-08-15"
    assert extract_target_date("3 days ago in Delhi", ref) == "2026-09-03"
    assert extract_target_date("2 weeks ago rainfall", ref) == "2026-08-23"
    assert extract_target_date("What was the temperature yesterday?", ref) == "2026-09-05"
    assert extract_target_date("day before yesterday weather", ref) == "2026-09-04"

    # Weekday offsets: 2026-09-06 is Sunday. Last Tuesday was 2026-09-01
    assert extract_target_date("Show me last Tuesday's rainfall", ref) == "2026-09-01"

    # Unspecified past intent defaults to yesterday
    assert extract_target_date("Historical weather records for Mumbai", ref) == "2026-09-05"
    assert extract_target_date("Did it rain in Chennai?", ref) == "2026-09-05"

    # Future / Present queries return None
    assert extract_target_date("Will it rain tomorrow in Kolkata?", ref) is None
    assert extract_target_date("What is the current temperature?", ref) is None


def test_detect_temporal_intent_past():
    """Verify that temporal intent classifier tags historical queries as 'past'."""
    assert detect_temporal_intent("How much did it rain in Kolkata on June 10, 2024?") == "past"
    assert detect_temporal_intent("What was the weather during Cyclone Amphan on May 20, 2020?") == "past"
    assert detect_temporal_intent("August 15, 1947 weather") == "past"
    assert detect_temporal_intent("Show me last Tuesday's rainfall") == "past"
    assert detect_temporal_intent("Yesterday's temperature in Mumbai") == "past"

    # Future and safety intent remain intact
    assert detect_temporal_intent("Will it rain tomorrow in Kolkata?") == "future"
    assert detect_temporal_intent("Is it safe to travel outside today?") == "safety"


def test_fetch_historical_data_archive():
    """Verify live Open-Meteo Global Historical Archive API retrieval back to 1947."""
    # Test 1: Cyclone Amphan (May 20, 2020) in Odisha
    rec_amphan = fetch_historical_data(20.9517, 85.0985, "2020-05-20")
    assert isinstance(rec_amphan, HistoricalWeatherRecord)
    assert rec_amphan.date == "2020-05-20"
    assert rec_amphan.max_temp is not None
    assert rec_amphan.total_precipitation is not None
    assert rec_amphan.total_precipitation > 10.0  # Heavy cyclone rain recorded
    assert rec_amphan.wind_max is not None
    assert rec_amphan.wind_max > 20.0  # Strong winds recorded
    assert "MoES Historical Archive / Open-Meteo" in rec_amphan.source

    # Test 2: August 15, 1947 in New Delhi
    rec_1947 = fetch_historical_data(28.6139, 77.2090, "1947-08-15")
    assert rec_1947.date == "1947-08-15"
    assert rec_1947.max_temp is not None
    assert rec_1947.min_temp is not None
    assert 20.0 < rec_1947.max_temp < 45.0


def test_query_with_schemas_historical_strict_data_gating():
    """Verify strict data gating: alerts nullified, live nowcasts suppressed, archive data cited."""
    brain = WeatherGPTBrain()

    # Active nowcast alert present in context
    live_alert = WeatherAlert(
        title="IMD 3-Hour Nowcast: Severe Thunderstorm Warning",
        description="Urgent nowcast: Intense squall wind reaching 55 km/h in next 3 hours.",
        severity="High",
        source="IMD",
    )

    query = "How much did it rain in Kolkata on June 10, 2024?"
    res = brain.query_with_schemas(
        request=ChatRequest(query=query),
        weather_data=None,  # Nullified for historical query
        location=Location(city="Kolkata", latitude=22.5726, longitude=88.3639),
        alerts=[live_alert],  # Should be strictly gated and nullified
    )

    # Gating checks
    assert res["alerts"] == [], "Active alerts must be strictly nullified for historical past queries"
    assert res["synoptic_overlays"] == [], "Live synoptic overlays must be suppressed for historical queries"

    # Source check
    source_names = [s.get("source") for s in res.get("sources", [])]
    assert any("MoES Historical Archive / Open-Meteo" in str(s) for s in source_names)

    # Reply content check
    reply = res["bot_reply"]
    assert "36." in reply or "June 10, 2024" in reply or "2024-06-10" in reply
    assert "Urgent nowcast" not in reply, "Active 3-hour nowcast must not leak into historical response"
    assert "next 3 hours" not in reply, "Active 3-hour alert text must not appear in historical response"


def test_live_chat_cyclone_amphan_and_kolkata_past():
    """Test live /chat endpoint with Cyclone Amphan and Kolkata past queries."""
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=25) as client:
        # Check server health
        health = client.get("/health")
        assert health.status_code == 200, "Dev server not healthy on http://127.0.0.1:8000"

        # Query 1: June 10, 2024 in Kolkata
        payload1 = {
            "query": "How much did it rain in Kolkata on June 10, 2024?",
            "location": {"city": "Kolkata"},
            "language": "en",
        }
        r1 = client.post("/chat", json=payload1)
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1["alerts"] == []
        reply1 = data1["bot_reply"]
        assert "3-hour nowcast" not in reply1.lower()
        assert any("MoES Historical Archive / Open-Meteo" in str(s.get("source")) for s in data1.get("sources", []))

        # Query 2: Cyclone Amphan (May 20, 2020)
        payload2 = {
            "query": "What was the weather in Odisha during Cyclone Amphan (May 20, 2020)?",
            "location": {"state": "Odisha"},
            "language": "en",
        }
        r2 = client.post("/chat", json=payload2)
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["alerts"] == []
        reply2 = data2["bot_reply"]
        assert any(term in reply2 for term in ["2020-05-20", "May 20, 2020", "Amphan", "18.", "26.", "29."])
        assert any("MoES Historical Archive / Open-Meteo" in str(s.get("source")) for s in data2.get("sources", []))


if __name__ == "__main__":
    print("Running test_extract_target_date_patterns()...")
    test_extract_target_date_patterns()
    print("PASS: test_extract_target_date_patterns")

    print("\nRunning test_detect_temporal_intent_past()...")
    test_detect_temporal_intent_past()
    print("PASS: test_detect_temporal_intent_past")

    print("\nRunning test_fetch_historical_data_archive()...")
    test_fetch_historical_data_archive()
    print("PASS: test_fetch_historical_data_archive")

    print("\nRunning test_query_with_schemas_historical_strict_data_gating()...")
    test_query_with_schemas_historical_strict_data_gating()
    print("PASS: test_query_with_schemas_historical_strict_data_gating")

    print("\nRunning test_live_chat_cyclone_amphan_and_kolkata_past()...")
    test_live_chat_cyclone_amphan_and_kolkata_past()
    print("PASS: test_live_chat_cyclone_amphan_and_kolkata_past")

    print("\n=========================================")
    print("ALL HISTORICAL ARCHIVE TESTS PASSED (5/5)!")
    print("=========================================")
