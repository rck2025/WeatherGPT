"""
Test Suite: Voice Hardening for Human Accents and Regional Accuracy.

Tests:
1. Task 1: Contextual Biasing (The 'Hint' System) & Native Script Initial Prompts.
2. Task 2: Acoustic Shielding (Dynamic Gain Control, True Peak -0.1 dB, Noise Gate).
3. Task 3: LID Override (Safety Net - UI Selection Priority over Whisper Confusion).
4. Task 4: Bhashini ASR Fallback for Top 5 Problematic Accent Languages (bn, ta, mr, te, ml).
5. Schemas & SIH Monitoring Fields (FullPipelineResponse, ChatResponse, TranscribeResponse).
"""
import os
import subprocess
import pytest
from unittest.mock import MagicMock, patch

from backend.schemas import ChatResponse, FullPipelineResponse
from backend.services.audio_utils import standardize_audio as audio_utils_standardize
from backend.services.language.bhashini_asr import (
    BHASHINI_ASR_SUPPORTED_LANGUAGES,
    bhashini_transcribe,
)
from backend.services.language.engine import (
    WEATHER_INITIAL_PROMPTS,
    WeatherHybridEngine,
    standardize_audio as engine_standardize,
)
from backend.services.language._schemas import TranscribeResponse
from backend.services.voice import transcribe as voice_transcribe, transcribe_audio


# ==============================================================================
# Task 1: Contextual Biasing (The 'Hint' System) & Initial Prompts
# ==============================================================================

def test_contextual_biasing_initial_prompts():
    """Verify WEATHER_INITIAL_PROMPTS contain top regional meteorological keywords."""
    assert "bn" in WEATHER_INITIAL_PROMPTS
    bn_prompt = WEATHER_INITIAL_PROMPTS["bn"]
    assert "বৃষ্টি" in bn_prompt
    assert "আবহাওয়া" in bn_prompt
    assert "ঘূর্ণিঝড়" in bn_prompt
    assert "কলকাতা" in bn_prompt

    assert "mr" in WEATHER_INITIAL_PROMPTS
    mr_prompt = WEATHER_INITIAL_PROMPTS["mr"]
    assert "पाऊस" in mr_prompt
    assert "हवामान" in mr_prompt
    assert "मुंबई" in mr_prompt

    assert "ta" in WEATHER_INITIAL_PROMPTS
    assert "மழை" in WEATHER_INITIAL_PROMPTS["ta"]
    assert "te" in WEATHER_INITIAL_PROMPTS
    assert "వర్షం" in WEATHER_INITIAL_PROMPTS["te"]
    assert "ml" in WEATHER_INITIAL_PROMPTS
    assert "മഴ" in WEATHER_INITIAL_PROMPTS["ml"]


def test_contextual_biasing_passes_language_and_initial_prompt(tmp_path):
    """Verify that when UI language is selected, Whisper is called with language and initial_prompt."""
    dummy_wav = tmp_path / "sample.wav"
    dummy_wav.write_bytes(b"RIFFdummydataWAVEfmt ")

    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_model = MagicMock()
    
    mock_info = MagicMock()
    mock_info.language = "bn"
    mock_info.language_probability = 0.92

    mock_segment = MagicMock()
    mock_segment.text = "আজ কলকাতায় বৃষ্টি হবে কি?"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_model
    engine.translate = MagicMock(return_value="Will it rain in Kolkata today?")

    with patch("backend.services.language.engine.standardize_audio", return_value=str(dummy_wav)):
        result = engine.process_query(str(dummy_wav), language_hint="bn")

    # Assert Whisper was called with language="bn" and the Bengali initial_prompt
    assert mock_model.transcribe.called
    kwargs = mock_model.transcribe.call_args.kwargs
    assert kwargs.get("language") == "bn"
    assert "বৃষ্টি" in kwargs.get("initial_prompt", "")
    assert "কলকাতা" in kwargs.get("initial_prompt", "")
    assert result["detected_lang"] == "bn"
    assert result["confidence"] == 0.92
    assert result["transcription_method"] == "Whisper"


# ==============================================================================
# Task 2: Acoustic Shielding & Audio Pre-processing
# ==============================================================================

def test_acoustic_shielding_filter_chain():
    """Verify acoustic shielding filter string contains noise gate and True Peak -0.1 dB."""
    import inspect
    from backend.services import audio_utils
    src = inspect.getsource(audio_utils.standardize_audio)
    assert "highpass=f=200" in src
    assert "lowpass=f=3000" in src
    assert "afftdn" in src
    assert "loudnorm=I=-16:TP=-0.1:LRA=11" in src


def test_engine_reexports_acoustic_shielding(tmp_path):
    """Verify backend.services.language.engine uses the acoustic shielding standardizer."""
    assert engine_standardize is audio_utils_standardize


# ==============================================================================
# Task 3: LID Override (Safety Net - UI Selection Priority)
# ==============================================================================

def test_lid_override_when_whisper_detects_mismatch(tmp_path):
    """
    If user explicitly selected Bengali ('bn'), but Whisper (confused by accent)
    returns Urdu ('ur'), system must override and force Bengali UI priority.
    """
    dummy_wav = tmp_path / "accent_mismatch.wav"
    dummy_wav.write_bytes(b"RIFFdummydataWAVEfmt ")

    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_model = MagicMock()

    # Whisper confused by human accent, detects 'ur'
    mock_info = MagicMock()
    mock_info.language = "ur"
    mock_info.language_probability = 0.55

    mock_segment = MagicMock()
    mock_segment.text = "আজ কলকাতায় বৃষ্টি হবে কি?"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_model
    engine.translate = MagicMock(return_value="Will it rain in Kolkata today?")

    with patch("backend.services.language.engine.standardize_audio", return_value=str(dummy_wav)), \
         patch("backend.services.language.engine.bhashini_transcribe", return_value=None):
        result = engine.process_query(str(dummy_wav), language_hint="bn")

    # The user selection must override Whisper's mistaken detection
    assert result["detected_lang"] == "bn"


# ==============================================================================
# Task 4: Bhashini ASR Fallback
# ==============================================================================

def test_bhashini_supported_languages_list():
    """Verify top 5 problematic accent languages are covered by Bhashini fallback."""
    for lang in ["bn", "ta", "mr", "te", "ml"]:
        assert lang in BHASHINI_ASR_SUPPORTED_LANGUAGES


def test_bhashini_fallback_triggered_on_low_confidence(tmp_path):
    """
    If Whisper confidence < 0.70 on one of top 5 languages, route to Bhashini ASR.
    When Bhashini succeeds, result has method 'Bhashini' and confidence 0.95.
    """
    dummy_wav = tmp_path / "low_conf.wav"
    dummy_wav.write_bytes(b"RIFFdummydataWAVEfmt ")

    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_model = MagicMock()

    # Whisper returns low confidence 0.42
    mock_info = MagicMock()
    mock_info.language = "bn"
    mock_info.language_probability = 0.42

    mock_segment = MagicMock()
    mock_segment.text = "garbled text"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_model
    engine.translate = MagicMock(return_value="How is the weather in Kolkata?")

    bhashini_mock_return = {
        "text": "আজ কলকাতায় আবহাওয়া কেমন?",
        "detected_lang": "bn",
        "confidence": 0.95,
        "transcription_method": "Bhashini",
    }

    with patch("backend.services.language.engine.standardize_audio", return_value=str(dummy_wav)), \
         patch("backend.services.language.engine.bhashini_transcribe", return_value=bhashini_mock_return) as mock_bhashini:
        result = engine.process_query(str(dummy_wav), language_hint="bn")

    mock_bhashini.assert_called_once_with(str(dummy_wav), target_lang="bn")
    assert result["transcription_method"] == "Bhashini"
    assert result["confidence"] == 0.95
    assert result["original_text"] == "আজ কলকাতায় আবহাওয়া কেমন?"
    assert result["detected_lang"] == "bn"


def test_whisper_retained_when_confidence_high(tmp_path):
    """When Whisper confidence >= 0.70, Bhashini is NOT invoked and Whisper is kept."""
    dummy_wav = tmp_path / "high_conf.wav"
    dummy_wav.write_bytes(b"RIFFdummydataWAVEfmt ")

    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_model = MagicMock()

    mock_info = MagicMock()
    mock_info.language = "mr"
    mock_info.language_probability = 0.88

    mock_segment = MagicMock()
    mock_segment.text = "पुण्यात उद्या पाऊस पडेल का?"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_model
    engine.translate = MagicMock(return_value="Will it rain in Pune tomorrow?")

    with patch("backend.services.language.engine.standardize_audio", return_value=str(dummy_wav)), \
         patch("backend.services.language.engine.bhashini_transcribe") as mock_bhashini:
        result = engine.process_query(str(dummy_wav), language_hint="mr")

    assert mock_bhashini.called is False
    assert result["transcription_method"] == "Whisper"
    assert result["confidence"] == 0.88
    assert result["detected_lang"] == "mr"


# ==============================================================================
# Public Interface & Schema Validation
# ==============================================================================

def test_voice_py_transcribe_interface(tmp_path):
    """Verify backend.services.voice.transcribe delegates cleanly."""
    dummy_wav = tmp_path / "voice_test.wav"
    dummy_wav.write_bytes(b"RIFFdummydataWAVEfmt ")

    with patch("backend.services.language.service.language_service.transcribe_audio") as mock_svc:
        mock_svc.return_value = {
            "original_text": "வானிலை எப்படி இருக்கிறது?",
            "detected_lang": "ta",
            "confidence": 0.91,
            "english_query": "How is the weather?",
            "transcription_method": "Whisper",
        }
        res1 = voice_transcribe(str(dummy_wav), language="ta")
        assert res1["detected_lang"] == "ta"
        assert res1["transcription_method"] == "Whisper"

        res2 = transcribe_audio(str(dummy_wav), language="ta")
        assert res2["confidence"] == 0.91


def test_schema_full_pipeline_response():
    """Verify FullPipelineResponse and ChatResponse contain transcription metrics."""
    resp = FullPipelineResponse(
        bot_reply="Today will be sunny.",
        transcription_method="Bhashini",
        transcription_confidence=0.95,
        detected_language="bn",
        transcribed_query="আজকে আবহাওয়া কেমন?",
    )
    assert resp.transcription_method == "Bhashini"
    assert resp.transcription_confidence == 0.95

    chat = ChatResponse(
        bot_reply="Today will be sunny.",
        transcription_method="Whisper",
        transcription_confidence=0.88,
    )
    assert chat.transcription_method == "Whisper"
    assert chat.transcription_confidence == 0.88

    transcribe_res = TranscribeResponse(
        success=True,
        original_text="टेस्ट",
        detected_language="mr",
        language_confidence=0.90,
        english_query="test",
        transcription_method="Whisper",
    )
    assert transcribe_res.transcription_method == "Whisper"
