"""
Test Suite: All 22 Scheduled Indian Languages Voice Hardening
Focuses on:
  - Odia (or / Oriya)
  - Konkani (kok)
  - Maithili (mai)
  - Bodo (brx)
  - Dogri (doi)
  - Kashmiri (ks)
  - Sindhi (sd)
  - Manipuri (mni)
  - Santali (sat)

Verifies:
  1. Whisper acoustic routing & fallback prevents ValueError on unsupported Whisper codes.
  2. Dropdown UI remains the Single Source of Truth (SSoT) locking detected_lang & locked_language_code.
  3. Odia phonetic Devanagari transliteration allows Edge-TTS hi-IN-SwaraNeural to speak native Odia.
  4. Regional voice routing & VoiceCleaner sanity.
  5. Number-to-word & meteorological unit expansions across Indic scripts.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.language.cleaner import (
    LANG_NUMBER_MAP_ALIASES,
    REGIONAL_VOICE_MAP,
    VoiceCleaner,
    get_voice_for_language,
    odia_to_phonetic_devanagari,
    prepare_for_tts,
    translate_units_to_native,
)
from backend.services.language.engine import (
    WEATHER_INITIAL_PROMPTS,
    WHISPER_LANGUAGE_CODE_MAP,
    WeatherHybridEngine,
)
from backend.services.voice import process_query


# =========================================================================
# 1. WHISPER ACOUSTIC MAPPING & SSoT PRESERVATION
# =========================================================================

TARGET_LANGS = ["kok", "mai", "brx", "doi", "ks", "sd", "mni", "sat", "or"]

@pytest.mark.parametrize("lang", TARGET_LANGS)
def test_whisper_acoustic_mapping_and_ssot(lang: str):
    """Ensure all 9 rare languages map to safe Whisper tokens and preserve SSoT."""
    expected_whisper = WHISPER_LANGUAGE_CODE_MAP[lang]
    
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_stt = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "Sample spoken weather query"
    mock_info = MagicMock()
    mock_info.language_probability = 0.96
    mock_stt.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_stt
    engine.translate = MagicMock(return_value="Sample english translation")

    with patch("backend.services.language.engine.standardize_audio", return_value="test.wav"), \
         patch("os.path.exists", return_value=True):
        res = engine.process_query("test.wav", target_lang=lang)

        # Transcribe was called with the acoustic surrogate (or None for Odia)
        mock_stt.transcribe.assert_called_once()
        _, kwargs = mock_stt.transcribe.call_args
        assert kwargs.get("language") == expected_whisper
        
        # Initial prompt contains weather keywords for that language
        assert lang in WEATHER_INITIAL_PROMPTS
        assert kwargs.get("initial_prompt") == WEATHER_INITIAL_PROMPTS[lang]

        # SSoT guarantee: returned code is the user's locked language
        assert res["detected_lang"] == lang
        assert res["locked_language_code"] == lang


def test_whisper_value_error_graceful_recovery():
    """Verify that if Whisper rejects any unexpected language code, it falls back to auto-detect."""
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_stt = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "ପାଣିପାଗ ସୂଚନା"
    mock_info = MagicMock()
    mock_info.language_probability = 0.92

    # First call raises ValueError, second call succeeds
    mock_stt.transcribe.side_effect = [
        ValueError("Invalid language code: custom"),
        ([mock_segment], mock_info),
    ]
    engine._stt_model = mock_stt
    engine.translate = MagicMock(return_value="Weather information")

    with patch("backend.services.language.engine.standardize_audio", return_value="test.wav"), \
         patch("os.path.exists", return_value=True):
        res = engine.process_query("test.wav", target_lang="custom")

        assert mock_stt.transcribe.call_count == 2
        # Second call retried with language=None
        _, second_kwargs = mock_stt.transcribe.call_args
        assert second_kwargs.get("language") is None
        assert res["locked_language_code"] == "custom"


# =========================================================================
# 2. ODIA PHONETIC DEVANAGARI TRANSLITERATION
# =========================================================================

def test_odia_to_phonetic_devanagari():
    """Verify Odia Unicode script transforms to Devanagari phonetically."""
    odia_text = "ପାଣିପାଗ ବର୍ଷା ତାପମାତ୍ରା"
    devanagari = odia_to_phonetic_devanagari(odia_text)

    # All Odia characters (U+0B00-U+0B7F) must be converted
    for ch in devanagari:
        code = ord(ch)
        assert not (0x0B00 <= code <= 0x0B7F), f"Found unmapped Odia character: {ch!r} ({hex(code)})"

    # Specific phonetic character mappings
    assert odia_to_phonetic_devanagari("ୟ") == "य"
    assert odia_to_phonetic_devanagari("ୱ") == "व"
    assert odia_to_phonetic_devanagari("ଡ଼") == "ड़"
    assert odia_to_phonetic_devanagari("ଢ଼") == "ढ़"


# =========================================================================
# 3. EDGE-TTS REGIONAL VOICE ROUTING
# =========================================================================

@pytest.mark.parametrize("lang,expected_voice", [
    ("or",  "hi-IN-SwaraNeural"),
    ("kok", "mr-IN-AarohiNeural"),
    ("mai", "hi-IN-SwaraNeural"),
    ("brx", "hi-IN-SwaraNeural"),
    ("doi", "hi-IN-SwaraNeural"),
    ("ks",  "ur-IN-GulNeural"),
    ("sd",  "ur-IN-GulNeural"),
    ("mni", "bn-IN-TanishaaNeural"),
    ("sat", "hi-IN-SwaraNeural"),
])
def test_regional_voice_selection(lang: str, expected_voice: str):
    """Verify Edge-TTS voice assignment for rare Indic languages."""
    voice = get_voice_for_language(lang)
    assert voice == expected_voice

    sanitized_voice, locked_lang = VoiceCleaner.sanitize_voice_for_script(
        voice_name=voice,
        text="Sample weather text",
        target_lang=lang,
    )
    assert sanitized_voice == expected_voice
    assert locked_lang == lang


# =========================================================================
# 4. NUMBER & METEOROLOGICAL UNIT EXPANSION
# =========================================================================

def test_odia_unit_and_number_expansion():
    """Verify Odia meteorological numbers & units expand into native words."""
    raw = "ତାପମାତ୍ରା ୨୯.୪°C ଏବଂ ପବନ ୧୫ km/h"
    # prepare_for_tts expands numbers and units
    prepared = prepare_for_tts(raw, lang="or")
    assert "29" not in prepared
    assert "°C" not in prepared
    assert "km/h" not in prepared


def test_translate_units_to_native_odia_converts_to_devanagari():
    """Verify translate_units_to_native produces Devanagari for Edge-TTS SwaraNeural."""
    raw_odia = "ଆଜି ଭୁବନେଶ୍ୱରରେ ତାପମାତ୍ରା ୩୨°C"
    spoken_odia = translate_units_to_native(raw_odia, lang="or")
    
    # Must not contain raw Odia characters because SwaraNeural requires phonetic Devanagari
    for ch in spoken_odia:
        code = ord(ch)
        assert not (0x0B00 <= code <= 0x0B7F), f"Found unconverted Odia char: {ch!r}"


# =========================================================================
# 5. END-TO-END TTS AUDIO PIPELINE FOR ODIA
# =========================================================================

@pytest.mark.asyncio
async def test_generate_regional_response_odia_phonetic():
    """Verify generate_regional_response converts Odia to phonetic Devanagari before calling Edge-TTS."""
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    engine.translate = MagicMock(return_value="ଭୁବନେଶ୍ୱରରେ ଆଜି ପ୍ରବଳ ବର୍ଷା ହେବାର ସମ୍ଭାବନା ଅଛି")

    mock_communicate = MagicMock()
    mock_communicate.save = AsyncMock()

    with patch("edge_tts.Communicate", return_value=mock_communicate) as mock_edge:
        res = await engine.generate_regional_response(
            raw_response="Heavy rain expected in Bhubaneswar today",
            target_lang="or",
            output_file="test_odia.mp3",
            source_is_english=True,
        )

        assert res["language"] == "or"
        assert res["voice_used"] == "hi-IN-SwaraNeural"

        # Check that the text sent to Edge-TTS is phonetic Devanagari (no Odia Unicode)
        sent_text, sent_voice = mock_edge.call_args[0]
        assert sent_voice == "hi-IN-SwaraNeural"
        for ch in sent_text:
            code = ord(ch)
            assert not (0x0B00 <= code <= 0x0B7F), f"Edge-TTS received raw Odia Unicode: {ch!r}"
