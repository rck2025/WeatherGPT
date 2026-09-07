"""
Test Suite: Deterministic Language Routing & Linguistic Hardening
Tests the 5 core tasks:
1. Explicit Language Routing: Mandatory/direct user_language without auto-detect coin-flips.
2. Zero LangID: langid is completely purged; no false positive Maltese/foreign classifications.
3. Romanization Conflict Resolution: Phonetic Latin/English letters for regional Indian languages are accepted.
4. Real Bhashini Fallback: Overwrites Whisper when empty or low-confidence (<0.50).
5. Bengali-to-Marathi Kill-Switch: Target synthesis language is locked strictly to user_language.
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.services.language.resolver import validate_script_alignment, detect_dominant_script
from backend.services.language.cleaner import REGIONAL_VOICE_MAP, VoiceCleaner
from backend.services.voice import process_query, transcribe
from backend.services.language.engine import WeatherHybridEngine
from backend.schemas import ChatRequest, LocationInput


# =========================================================================
# TASK 1: Explicit Language Routing & Auto-Detect Disablement
# =========================================================================

def test_explicit_language_routing_disables_autodetect():
    """Verify that when user_language is specified, Whisper receives language=user_language directly."""
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_stt = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "কালকের আবহাওয়া কেমন"
    mock_info = MagicMock()
    mock_info.language_probability = 0.98
    mock_info.language = "bn"
    mock_stt.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_stt
    engine.translate = MagicMock(return_value="How is tomorrow's weather")

    with patch("backend.services.language.engine.standardize_audio", return_value="dummy.wav"), \
         patch("os.path.exists", return_value=True):
        res = engine.process_query("dummy.wav", user_language="bn")

        # Confirm transcribe was called with language='bn' (not None)
        mock_stt.transcribe.assert_called_once()
        _, kwargs = mock_stt.transcribe.call_args
        assert kwargs.get("language") == "bn"
        assert "বৃষ্টি" in kwargs.get("initial_prompt", "")
        assert res["detected_lang"] == "bn"
        assert res["locked_language_code"] == "bn"


def test_voice_py_transcribe_accepts_user_language():
    """Verify voice.py transcribe forwards user_language."""
    with patch("backend.services.voice.language_service.transcribe_audio") as mock_transcribe:
        mock_transcribe.return_value = {
            "original_text": "पाऊस पडेल का",
            "detected_lang": "mr",
            "confidence": 0.95,
            "english_query": "Will it rain",
            "transcription_method": "Whisper",
        }
        res = transcribe("dummy.wav", user_language="mr")
        mock_transcribe.assert_called_once_with(
            "dummy.wav",
            language_hint="mr",
            user_language="mr",
        )
        assert res["detected_lang"] == "mr"
        assert res["locked_language_code"] == "mr"


# =========================================================================
# TASK 2: Cleanup the Noise (Zero LangID Dependency)
# =========================================================================

def test_zero_langid_in_resolver():
    """Verify resolver.py operates deterministically without importing or calling langid."""
    import backend.services.language.resolver as resolver

    # Ensure langid is not in globals or imported by resolver
    assert "langid" not in resolver.__dict__

    # Test Devanagari disambiguation uses markers deterministically
    marathi_text = "उद्या मुंबईमध्ये पाऊस पडेल का"
    lang, script, purity = detect_dominant_script(marathi_text)
    assert lang == "mr"
    assert script == "Devanagari"
    assert purity > 0.5


# =========================================================================
# TASK 3: Fix Romanization / Script Conflict
# =========================================================================

def test_romanized_phonetic_input_accepted_for_bengali():
    """Phonetic Romanized text for Bengali ('Kalker Abu Hawa') must not be rejected."""
    # Romanized phonetic input with English letters
    is_valid, msg = validate_script_alignment("Kalker Abu Hawa", "bn")
    assert is_valid is True
    assert msg == "OK"

    # With punctuation and trailing characters
    is_valid, msg = validate_script_alignment("Kalker Abu Hawaq Amon Hawaq", "bn")
    assert is_valid is True
    assert msg == "OK"


def test_romanized_phonetic_input_accepted_for_marathi_and_hindi():
    """Phonetic Romanized text for Marathi/Hindi must be accepted."""
    is_valid, msg = validate_script_alignment("Paus padel ka udya", "mr")
    assert is_valid is True
    assert msg == "OK"

    is_valid, msg = validate_script_alignment("Mausam kaisa rahega", "hi")
    assert is_valid is True
    assert msg == "OK"


def test_cjk_hallucination_still_rejected():
    """CJK / Japanese hallucinations must still be strictly rejected."""
    is_valid, msg = validate_script_alignment("カルケル ウェデル", "bn")
    assert is_valid is False
    assert "SCRIPT_MISMATCH: Detected CJK" in msg


# =========================================================================
# TASK 4: Real Bhashini Fallback & Overwrite
# =========================================================================

def test_bhashini_fallback_overwrites_low_confidence_in_automode():
    """When Whisper confidence is < 0.50 in auto-mode, Bhashini overwrites result."""
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_stt = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "whisper noisy text"
    mock_info = MagicMock()
    mock_info.language_probability = 0.22  # Low confidence < 0.50
    mock_info.language = "bn"
    mock_info.all_language_probs = [("bn", 0.22), ("hi", 0.15)]
    mock_stt.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_stt
    engine.translate = MagicMock(return_value="Will it rain tomorrow")

    mock_bhashini_result = {
        "text": "কাল কি বৃষ্টি হবে",
        "detected_lang": "bn",
        "confidence": 0.94,
        "transcription_method": "Bhashini",
    }

    with patch("backend.services.language.engine.standardize_audio", return_value="dummy.wav"), \
         patch("backend.services.language.engine.bhashini_transcribe", return_value=mock_bhashini_result), \
         patch("backend.services.language.engine.clean_transcribed_input", side_effect=lambda x: x), \
         patch("os.path.exists", return_value=True):

        res = engine.process_query("dummy.wav", language_hint="auto")

        # Bhashini must explicitly overwrite Whisper text and method
        assert res["original_text"] == "কাল কি বৃষ্টি হবে"
        assert res["transcription_method"] == "Bhashini"
        assert res["transcription_source"] == "Bhashini"
        assert res["confidence"] == 0.94
        assert res["detected_lang"] == "bn"


# =========================================================================
# TASK 5: The Bengali-to-Marathi Kill-Switch
# =========================================================================

def test_synthesis_killswitch_strictly_locks_user_language():
    """Even if text contains Roman or Devanagari characters, user_language='bn' forces Bengali voice."""
    import asyncio
    from backend.main import execute_weather_logic

    # Simulated request where user explicitly chose Bengali in UI
    chat_req = ChatRequest(
        query="কালকের আবহাওয়া কেমন হবে",
        location=LocationInput(raw_text="Kolkata"),
        language="bn",
        channel="voice",
    )

    with patch("backend.main.rag_service.answer") as mock_answer, \
         patch("backend.main.open_meteo_service.get_weather") as mock_weather, \
         patch("backend.main.language_service.translate_query_to_english", return_value="How is tomorrow's weather"), \
         patch("backend.main.location_resolver.resolve", return_value=MagicMock(latitude=22.57, longitude=88.36, city="Kolkata")), \
         patch("backend.main.weather_history_service.fetch_time_series", return_value=([], "summary")), \
         patch("backend.main.language_service.synthesize_audio") as mock_synthesize:

        mock_resp = MagicMock()
        mock_resp.bot_reply = "কাল কলকাতায় সারাদিন রোদ থাকবে।"
        mock_resp.alerts = []
        mock_resp.sources = []
        mock_resp.synoptic_overlays = []
        mock_answer.return_value = mock_resp
        mock_synthesize.return_value = "/voice/audio/test_bn.mp3"

        resp = asyncio.run(execute_weather_logic(chat_req))

        # Confirm synthesis was invoked strictly with target_lang='bn'
        mock_synthesize.assert_called_once()
        _, kwargs = mock_synthesize.call_args
        assert kwargs.get("target_lang") == "bn"
        assert resp.locked_language_code == "bn"
        assert resp.detected_language == "bn"


def test_voice_cleaner_marathi_to_bengali_script_killswitch():
    """VoiceCleaner auto-corrects Marathi voice to bn-IN-TanishaaNeural if text has Bengali script."""
    voice, lang = VoiceCleaner.sanitize_voice_for_script(
        voice_name="mr-IN-AarohiNeural",
        text="বৃষ্টি হওয়ার সম্ভাবনা আছে",
        target_lang="mr",
    )
    assert voice == "bn-IN-TanishaaNeural"
    assert lang == "bn"
