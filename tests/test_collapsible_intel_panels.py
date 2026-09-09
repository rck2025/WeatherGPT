"""
Test Collapsible Intel Panels & Action Buttons:
1. Verifies BTN_SOURCES and BTN_HAZARDS exist across all 15 scheduled languages in UI_LOCALE.
2. Verifies frontend/style.css terminal inversion and styling rules for .intel-toggle-btn and .intel-panel-content.
3. Verifies frontend/app.js implements updateIntelToggleText, toggleIntelPanel, and collapsible panels.
4. Verifies endpoint /chat returns sources and alerts for collapsible rendering.
"""

import json
import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

SCHEDULED_LANGUAGES = [
    "en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "ur", "pa", "or", "as", "ne", "sa"
]


def load_ui_locale_dict():
    """Extract and parse UI_LOCALE from frontend/ui_translations.js"""
    js_path = Path("frontend/ui_translations.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    match = re.search(r"const\s+UI_LOCALE\s*=\s*(\{[\s\S]+?\n\};)", content)
    assert match, "Could not find UI_LOCALE definition in ui_translations.js"
    raw_obj = match.group(1).rstrip(";").strip()

    cleaned = re.sub(r'(\n\s*)([A-Za-z0-9_]+)\s*:', r'\1"\2":', raw_obj)
    cleaned = re.sub(r',\s*\}', '}', cleaned)

    return json.loads(cleaned)


def test_ui_locale_contains_intel_panel_keys_in_all_15_languages():
    """Verify BTN_SOURCES and BTN_HAZARDS exist in all 15 languages."""
    locale = load_ui_locale_dict()
    for lang in SCHEDULED_LANGUAGES:
        assert lang in locale, f"Missing language {lang} in UI_LOCALE"
        lang_dict = locale[lang]
        assert "BTN_SOURCES" in lang_dict, f"Missing BTN_SOURCES in {lang}"
        assert "BTN_HAZARDS" in lang_dict, f"Missing BTN_HAZARDS in {lang}"
        assert len(lang_dict["BTN_SOURCES"].strip()) > 0
        assert len(lang_dict["BTN_HAZARDS"].strip()) > 0


def test_english_and_tamil_intel_labels():
    """Verify English and Tamil button label strings."""
    locale = load_ui_locale_dict()
    assert locale["en"]["BTN_SOURCES"] == "SOURCES // INTEL"
    assert locale["en"]["BTN_HAZARDS"] == "RADAR HAZARDS"
    assert "SOURCES" in locale["ta"]["BTN_SOURCES"] or "ஆதாரங்கள்" in locale["ta"]["BTN_SOURCES"]
    assert "RADAR HAZARDS" in locale["ta"]["BTN_HAZARDS"] or "ரேடார்" in locale["ta"]["BTN_HAZARDS"]


def test_style_css_terminal_inversion_and_rules():
    """Verify style.css implements terminal inversion, 0.75rem font size, and 1px green border."""
    css_path = Path("frontend/style.css")
    assert css_path.exists()
    css = css_path.read_text(encoding="utf-8")

    assert ".intel-toggle-bar" in css
    assert ".intel-toggle-btn" in css
    assert ".intel-panel-content" in css

    # Verify terminal inversion on hover: background turns #00FF41, text turns #000000
    hover_match = re.search(r"\.intel-toggle-btn:hover\s*\{([^}]+)\}", css)
    assert hover_match, "Missing .intel-toggle-btn:hover definition"
    hover_body = hover_match.group(1)
    assert "#00FF41" in hover_body or "var(--terminal-green" in hover_body
    assert "#000000" in hover_body or "black" in hover_body

    # Verify font-size 0.75rem and border 1px solid #00FF41
    btn_match = re.search(r"\.intel-toggle-btn\s*\{([^}]+)\}", css)
    assert btn_match, "Missing .intel-toggle-btn definition"
    btn_body = btn_match.group(1)
    assert "0.75rem" in btn_body
    assert "#00FF41" in btn_body


def test_app_js_collapsible_panel_logic():
    """Verify app.js defines updateIntelToggleText, toggleIntelPanel, and handles BTN_SOURCES/BTN_HAZARDS."""
    app_js_path = Path("frontend/app.js")
    assert app_js_path.exists()
    content = app_js_path.read_text(encoding="utf-8")

    assert "function updateIntelToggleText(" in content
    assert "function toggleIntelPanel(" in content
    assert "intel-panel-content" in content
    assert "intel-toggle-btn" in content
    assert "data-state" in content
    assert "BTN_SOURCES" in content
    assert "BTN_HAZARDS" in content


def test_chat_endpoint_populates_sources_and_hazards_for_intel_panels():
    """Verify /chat endpoint returns both sources and hazards when queried."""
    payload = {
        "query": "Kolkata weather and active cyclone or flood alerts",
        "language": "en",
        "channel": "web",
        "location": {"latitude": 22.5726, "longitude": 88.3639, "city": "Kolkata"},
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "bot_reply" in data
    assert "sources" in data
    assert "alerts" in data
    assert isinstance(data["sources"], list)
    assert isinstance(data["alerts"], list)
