"""Unit and integration tests for ESA WorldCover 10m Cropland Satellite Mask ("Agri-Scan")."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.weather.gee_service import gee_service, get_cropland_mask_url
from backend.services.rag.service import farmer_template, build_agromet_scientist_briefing
from backend.schemas import Location


def test_cropland_mask_url_generation():
    """Verify get_cropland_mask_url returns a valid GEE Leaflet XYZ tile URL."""
    # Ensure GEE initialized with service account
    assert gee_service.ensure_initialized() is True
    
    url = get_cropland_mask_url()
    assert isinstance(url, str)
    assert "earthengine.googleapis.com" in url
    assert "{z}/{x}/{y}" in url


def test_cropland_map_layer_endpoint():
    """Verify /api/v1/map/layers/cropland returns 200 and correct layer metadata."""
    client = TestClient(app)
    response = client.get("/api/v1/map/layers/cropland")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["layer_id"] == "cropland"
    assert "ESA WorldCover 10m" in data["source"]
    assert data["opacity"] == 0.6
    assert "earthengine.googleapis.com" in data["tile_url"]
    assert "{z}/{x}/{y}" in data["tile_url"]


def test_farmer_prompt_cropland_intelligence_link():
    """Verify the Farmer Mode system prompt contains the ESA WorldCover 10m Cropland Mask directive."""
    assert "You are viewing the ESA WorldCover 10m Cropland Mask" in farmer_template
    assert "exact boundaries of agricultural land" in farmer_template
    assert "field-specific advice" in farmer_template


def test_agromet_briefing_cropland_grounding():
    """Verify build_agromet_scientist_briefing incorporates ESA WorldCover 10m Grounding."""
    loc = Location(city="Ludhiana", latitude=30.9, longitude=75.85)
    briefing = build_agromet_scientist_briefing(
        location=loc,
        temp_c=29.0,
        humidity=72.0,
        wind_spd=11.0,
        soil_vwc=0.35,
        weather_code=0,
        rain_expected=False,
    )
    assert "ESA WorldCover 10m" in briefing
    assert "Cropland Parcel Grounding" in briefing
