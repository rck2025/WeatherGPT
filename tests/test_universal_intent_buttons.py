"""
Test Universal Intent-Based Quick Action Buttons:
1. Validates UI_LOCALE keys (QUERY_SAFETY, QUERY_RAIN, QUERY_HISTORY, QUERY_CROP) across all 15 languages.
2. Validates index.html quick-action buttons and attributes.
3. Validates app.js sendQuickQuery implementation.
4. Validates Task 4 Dynamic Routing:
   - 'How was the weather yesterday?' -> PAST_HISTORICAL
   - Tamil 'நேற்று வானிலை எப்படி இருந்தது?' -> PAST_HISTORICAL
   - Hindi 'कल मौसम कैसा था?' -> PAST_HISTORICAL
   - 'Will it rain in the next hour?' -> FUTURE_FORECAST
   - Safety queries triggering safety evaluation.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.rag.brain import extract_target_date
from backend.services.rag.controller import (
    SovereignLogicController,
    TemporalCategory,
    IST,
)

client = TestClient(app)

SCHEDULED_LANGUAGES = [
    "en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "ur", "pa", "or", "as", "ne", "sa"
]

INTENT_KEYS = [
    "QUERY_SAFETY",
    "QUERY_RAIN",
    "QUERY_HISTORY",
    "QUERY_CROP",
]


def load_ui_locale_dict():
    """Extract and parse UI_LOCALE from frontend/ui_translations.js"""
    js_path = Path("frontend/ui_translations.js")
    assert js_path.exists(), "frontend/ui_translations.js not found!"
    content = js_path.read_text(encoding="utf-8")

    # Match UI_LOCALE = { ... };
    match = re.search(r"const\s+UI_LOCALE\s*=\s*(\{[\s\S]+?\n\};)", content)
    assert match, "Could not find UI_LOCALE definition in ui_translations.js"
    raw_obj = match.group(1).rstrip(";").strip()

    # Convert JS object syntax to valid JSON:
    # 1. Quote unquoted keys (e.g. en: { -> "en": {)
    cleaned = re.sub(r'(\n\s*)([A-Za-z0-9_]+)\s*:', r'\1"\2":', raw_obj)
    # 2. Remove trailing commas before }
    cleaned = re.sub(r',\s*\}', '}', cleaned)

    return json.loads(cleaned)


def test_ui_locale_contains_all_15_languages():
    """Verify all 15 scheduled languages are present in UI_LOCALE."""
    locale = load_ui_locale_dict()
    for lang in SCHEDULED_LANGUAGES:
        assert lang in locale, f"Language '{lang}' is missing from UI_LOCALE!"


def test_ui_locale_contains_all_four_intent_keys_in_all_languages():
    """Verify QUERY_SAFETY, QUERY_RAIN, QUERY_HISTORY, QUERY_CROP exist in all 15 languages."""
    locale = load_ui_locale_dict()
    for lang in SCHEDULED_LANGUAGES:
        lang_dict = locale[lang]
        for key in INTENT_KEYS:
            assert key in lang_dict, f"Missing key '{key}' in language '{lang}'!"
            val = lang_dict[key].strip()
            assert len(val) > 0, f"Empty value for key '{key}' in language '{lang}'!"


def test_tamil_intent_translations_exact_match():
    """Verify Tamil translations match user specification."""
    locale = load_ui_locale_dict()
    ta = locale["ta"]
    assert ta["QUERY_SAFETY"] == "இப்போது வெளியே செல்வது பாதுகாப்பானதா?"
    assert "மழை" in ta["QUERY_RAIN"]  # rain
    assert "நேற்று" in ta["QUERY_HISTORY"]  # yesterday
    assert "வேளாண்" in ta["QUERY_CROP"] or "Agromet" in ta["QUERY_CROP"]  # Agromet / agriculture


def test_english_intent_translations():
    """Verify English values match expected human-intent queries."""
    locale = load_ui_locale_dict()
    en = locale["en"]
    assert en["QUERY_SAFETY"] == "Is it safe to go out right now?"
    assert en["QUERY_RAIN"] == "Will it rain in the next hour?"
    assert en["QUERY_HISTORY"] == "How was the weather yesterday?"
    assert "crop advisory" in en["QUERY_CROP"].lower()


def test_index_html_quick_actions_markup():
    """Verify index.html contains four buttons with data-t, quick-prompt-btn class, and onclick handler."""
    html_path = Path("frontend/index.html")
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    for key in INTENT_KEYS:
        pattern = rf'<button[^>]+class="[^"]*quick-prompt-btn[^"]*"[^>]+data-t="{key}"[^>]+onclick="sendQuickQuery\(this\.textContent\)"'
        alt_pattern = rf'<button[^>]+data-t="{key}"[^>]+onclick="sendQuickQuery\(this\.textContent\)"'
        assert re.search(pattern, content) or re.search(alt_pattern, content), (
            f"Button with data-t='{key}', class='quick-prompt-btn', and onclick='sendQuickQuery(this.textContent)' not found in index.html"
        )


def test_app_js_defines_send_quick_query():
    """Verify app.js defines sendQuickQuery and exposes it on window."""
    app_js_path = Path("frontend/app.js")
    assert app_js_path.exists()
    content = app_js_path.read_text(encoding="utf-8")

    assert "function sendQuickQuery(" in content, "sendQuickQuery function missing in app.js"
    assert "window.sendQuickQuery = sendQuickQuery" in content, "window.sendQuickQuery not exposed in app.js"


def test_history_intent_triggers_past_historical_in_controller():
    """Task 4: Ensure English and Indic 'History' button queries trigger PAST_HISTORICAL."""
    controller = SovereignLogicController()
    now_ist = datetime(2026, 9, 8, 14, 0, tzinfo=IST)
    yesterday_str = (now_ist - timedelta(days=1)).strftime("%Y-%m-%d")

    queries_to_test = [
        ("How was the weather yesterday?", "en"),
        ("कल मौसम कैसा था?", "hi"),
        ("நேற்று வானிலை எப்படி இருந்தது?", "ta"),
        ("গতকাল আবহাওয়া কেমন ছিল?", "bn"),
        ("काल हवामान कसे होते?", "mr"),
        ("నిన్న వాతావరణం ఎలా ఉండింది?", "te"),
        ("ગઈકાલે હવામાન કેવું હતું?", "gu"),
    ]

    for q, lang in queries_to_test:
        decision = controller.categorize_query(q, lang_code=lang, ref_time=now_ist)
        assert decision.category == TemporalCategory.PAST_HISTORICAL, (
            f"Query '{q}' ({lang}) failed to route to PAST_HISTORICAL! Got: {decision.category}"
        )
        assert decision.target_date == yesterday_str, (
            f"Query '{q}' target date mismatch! Expected {yesterday_str}, got: {decision.target_date}"
        )


def test_rain_intent_triggers_future_forecast_in_controller():
    """Verify 'Will it rain in the next hour?' triggers FUTURE_FORECAST."""
    controller = SovereignLogicController()
    now_ist = datetime(2026, 9, 8, 14, 0, tzinfo=IST)

    decision_en = controller.categorize_query("Will it rain in the next hour?", lang_code="en", ref_time=now_ist)
    assert decision_en.category == TemporalCategory.FUTURE_FORECAST
    assert decision_en.minute_offset == 60


def test_safety_intent_query_endpoint():
    """Verify sending Tamil safety query to /chat returns a valid response."""
    payload = {
        "query": "இப்போது வெளியே செல்வது பாதுகாப்பானதா?",
        "language": "ta",
        "channel": "web",
        "location": {"latitude": 13.0827, "longitude": 80.2707, "city": "Chennai"},
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "bot_reply" in data
    assert len(data["bot_reply"]) > 0
