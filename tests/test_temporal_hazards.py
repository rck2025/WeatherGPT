"""Comprehensive Test Suite for Visual Temporal Map Filter & Historical Hazard Dashboard."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone, timedelta
import httpx

from backend.schemas import WeatherAlert
from backend.services.weather.hazards import get_realtime_hazards


def test_schema_weather_alert_temporal_fields():
    """Verify that WeatherAlert correctly supports is_historical and occurred_at."""
    now = datetime.now(timezone.utc)
    live_alert = WeatherAlert(
        title="Live Alert",
        description="Active now",
        severity="High",
        source="IMD",
        latitude=22.5726,
        longitude=88.3639,
        is_historical=False,
        occurred_at=now,
    )
    assert live_alert.is_historical is False
    assert live_alert.occurred_at == now

    hist_alert = WeatherAlert(
        title="Past Earthquake M5.4",
        description="Recorded 2 days ago",
        severity="Moderate",
        source="USGS",
        latitude=27.7,
        longitude=85.3,
        is_historical=True,
        occurred_at=now - timedelta(days=2),
    )
    assert hist_alert.is_historical is True
    assert hist_alert.occurred_at < now


def test_get_realtime_hazards_intervals():
    """Verify temporal window filtering across 1h, 6h, 24h, and 7d."""
    h_1h = get_realtime_hazards(interval="1h")
    h_24h = get_realtime_hazards(interval="24h")
    h_7d = get_realtime_hazards(interval="7d")

    print(f"1h Count: {len(h_1h)}, 24h Count: {len(h_24h)}, 7d Count: {len(h_7d)}")

    # 1. 7D must return 20+ seismic & weather hazards (proving spatial-temporal climate trend)
    assert len(h_7d) >= 20, f"Expected at least 20 markers for 7D, got {len(h_7d)}"

    # 2. 7D count must exceed 24h count
    assert len(h_7d) >= len(h_24h)

    # 3. Verify presence of both live and historical markers in 7D
    historical_7d = [h for h in h_7d if h.is_historical]
    live_7d = [h for h in h_7d if not h.is_historical]
    assert len(historical_7d) >= 15, "Expected majority of 7D events to be flagged as historical"
    assert len(live_7d) >= 1, "Expected at least 1 live active event"

    # 4. Verify all alerts have occurred_at timestamp
    for alert in h_7d:
        assert alert.occurred_at is not None, f"Alert {alert.title} missing occurred_at"


def test_live_hazards_endpoint():
    """Verify GET /hazards endpoint with interval filtering and telemetry summary."""
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=20) as client:
        # Check health
        health = client.get("/health")
        assert health.status_code == 200

        # Query /hazards with 7d interval
        res = client.get("/hazards?interval=7d&lat=22.5726&lon=88.3639")
        assert res.status_code == 200
        data = res.json()

        assert data["interval"] == "7d"
        assert data["count"] >= 20, f"Expected at least 20 hazards for 7D, got {data['count']}"
        assert len(data["hazards"]) == data["count"]

        # Check telemetry summary sync
        summary = data.get("summary")
        assert summary is not None
        assert "avg_temperature" in summary
        assert "avg_humidity" in summary
        assert summary["avg_temperature"] > 0

        # Verify historical vs live count
        hist_count = sum(1 for h in data["hazards"] if h.get("is_historical"))
        assert hist_count >= 15


if __name__ == "__main__":
    print("Running test_schema_weather_alert_temporal_fields()...")
    test_schema_weather_alert_temporal_fields()
    print("PASS: test_schema_weather_alert_temporal_fields")

    print("\nRunning test_get_realtime_hazards_intervals()...")
    test_get_realtime_hazards_intervals()
    print("PASS: test_get_realtime_hazards_intervals")

    print("\nRunning test_live_hazards_endpoint()...")
    test_live_hazards_endpoint()
    print("PASS: test_live_hazards_endpoint")

    print("\n=========================================")
    print("ALL TEMPORAL HAZARD TESTS PASSED (3/3)!")
    print("=========================================")
