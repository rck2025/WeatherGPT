"""Tests for Google Earth Engine (GEE) Satellite Vision Service and Endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.services.weather.gee_service import GEEService


@pytest.fixture
def client():
    return TestClient(app)


def test_gee_endpoints_success(client):
    # Test Thermal Layer
    r_thermal = client.get("/api/v1/map/layers/thermal")
    assert r_thermal.status_code == 200
    data_t = r_thermal.json()
    assert data_t["status"] == "success"
    assert data_t["layer_id"] == "thermal"
    assert "tile_url" in data_t
    assert data_t["tile_url"].startswith("https://earthengine.googleapis.com/")

    # Test Precipitation Layer
    r_precip = client.get("/api/v1/map/layers/precipitation")
    assert r_precip.status_code == 200
    data_p = r_precip.json()
    assert data_p["status"] == "success"
    assert data_p["layer_id"] == "precipitation"
    assert "tile_url" in data_p
    assert data_p["tile_url"].startswith("https://earthengine.googleapis.com/")

    # Test Scientific Composite Layer
    r_composite = client.get("/api/v1/map/layers/scientific_composite")
    assert r_composite.status_code == 200
    data_c = r_composite.json()
    assert data_c["status"] == "success"
    assert data_c["layer_id"] == "scientific_composite"
    assert "tile_url" in data_c
    assert data_c["tile_url"].startswith("https://earthengine.googleapis.com/")

    # Test Low Pressure Aura Layer
    r_pressure = client.get("/api/v1/map/layers/low_pressure")
    assert r_pressure.status_code == 200
    data_pr = r_pressure.json()
    assert data_pr["status"] == "success"
    assert data_pr["layer_id"] == "low_pressure"
    assert "tile_url" in data_pr
    assert data_pr["tile_url"].startswith("https://earthengine.googleapis.com/")

    # Test Area Stats
    r_stats = client.get("/api/v1/map/stats?lat=22.5726&lon=88.3639&radius_km=10")
    assert r_stats.status_code == 200
    data_s = r_stats.json()
    assert "sector_verification" in data_s
    assert "Satellite verification" in data_s["sector_verification"] or "Orbital" in data_s["sector_verification"]


def test_gee_endpoint_unknown_layer(client):
    r = client.get("/api/v1/map/layers/invalid_layer")
    assert r.status_code == 404
    assert "Unknown satellite layer" in r.json()["detail"]


def test_gee_uninitialized_graceful_handling():
    uninit_service = GEEService(key_path="non_existent_key.json")
    assert uninit_service.initialized is False
    stats = uninit_service.get_area_stats(22.5726, 88.3639)
    assert stats["mean_ground_temp_c"] is None
    assert "unavailable" in stats["sector_verification"]
