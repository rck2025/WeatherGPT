"""
Test Suite: Linguistic Lock and Anti-Drift Engine.

Verifies:
1. Task 1: Linguistic Passport (locked_language_code field and verified ISO code).
2. Task 2: Explicit Voice Mapping ('bn' -> Tanishaa, 'mr' -> Aarohi, no 'auto' in synthesis).
3. Task 3: Translation Hallucination & Language Drift Check (bn -> mr drift raises warning and reverts to bn).
4. Task 4: Closed-Loop Full Pipeline Endpoint (/api/voice/full-pipeline returns locked_language_code).
5. Task 5: Pre-Synthesis Script Guardian (Bengali text with Marathi voice auto-corrects to bn-IN-TanishaaNeural).
"""
import pytest
import warnings
from unittest.mock import MagicMock, patch

from backend.schemas import ChatResponse, FullPipelineResponse
from backend.services.cleaner import (
    REGIONAL_VOICE_MAP,
    VoiceCleaner,
    get_voice_for_language,
    safe_translate,
)
from backend.services.language.translator import translate_text
from backend.services.voice import process_query, transcribe


def test_linguistic_passport_schema():
    """Verify locked_language_code is in FullPipelineResponse and ChatResponse."""
    fp = FullPipelineResponse(
        bot_reply="আজকের আবহাওয়া রৌদ্রোজ্জ্বল।",
        locked_language_code="bn",
        detected_language="bn",
    )
    assert fp.locked_language_code == "bn"
    assert fp.detected_language == "bn"

    chat = ChatResponse(
        bot_reply="আজকের আবহাওয়া রৌদ্রোজ্জ্বল।",
        locked_language_code="bn",
    )
    assert chat.locked_language_code == "bn"


def test_voice_py_process_query_verified_iso(tmp_path):
    """Verify backend.services.voice.process_query returns normalized, verified ISO code."""
    dummy_wav = tmp_path / "test.wav"
    dummy_wav.write_bytes(b"RIFFdata")

    with patch("backend.services.language.service.language_service.transcribe_audio") as mock_stt:
        mock_stt.return_value = {
            "original_text": "আজ কলকাতায় বৃষ্টি হবে কি?",
            "detected_lang": "bn-IN",
            "confidence": 0.94,
            "english_query": "Will it rain in Kolkata today?",
            "transcription_method": "Whisper",
        }
        res = process_query(str(dummy_wav), language_hint="bn")
        assert res["detected_lang"] == "bn"
        assert res["locked_language_code"] == "bn"


def test_explicit_voice_mapping():
    """Verify 'bn' maps strictly to Tanishaa and 'mr' to Aarohi, and auto is rejected."""
    assert REGIONAL_VOICE_MAP["bn"] == "bn-IN-TanishaaNeural"
    assert REGIONAL_VOICE_MAP["mr"] == "mr-IN-AarohiNeural"

    assert get_voice_for_language("bn") == "bn-IN-TanishaaNeural"
    assert get_voice_for_language("mr") == "mr-IN-AarohiNeural"

    # Synthesis must prohibit 'auto'
    with pytest.raises(ValueError, match="Linguistic Lock"):
        get_voice_for_language("auto")

    with pytest.raises(ValueError, match="Linguistic Lock"):
        get_voice_for_language("none")


def test_language_drift_prevention_safe_translate():
    """Verify that if input is Bengali and target is Marathi, warning is raised and reverted to bn."""
    with pytest.warns(UserWarning, match="Potential Language Drift Detected. Reverting to BN."):
        # Bengali query text mistakenly requested to be translated to Marathi
        bengali_text = "আজ কলকাতায় বৃষ্টি হবে কি?"
        # Both input_lang='bn' and script detection trigger the safety net
        res = safe_translate(bengali_text, source_lang="bn", target_lang="mr", input_lang="bn")
        # Since target reverted to 'bn' and source was 'bn', text is returned intact without translating to Marathi
        assert "আজ" in res or res == bengali_text


def test_language_drift_prevention_translate_text():
    """Verify translate_text also blocks bn -> mr drift."""
    with pytest.warns(UserWarning, match="Potential Language Drift Detected. Reverting to BN."):
        res = translate_text("আজ বৃষ্টি হবে", source_lang="bn", target_lang="mr")
        assert res == "আজ বৃষ্টি হবে"


def test_pre_synthesis_script_check_guardian():
    """
    Task 5: If the text to be spoken is Bengali (Eastern Nagari) but voice is Marathi (mr-IN-AarohiNeural),
    trigger automatic Voice Correction to bn-IN-TanishaaNeural and language 'bn'.
    """
    bengali_spoken_text = "আজকের তাপমাত্রা উনত্রিশ দশমিক চার ডিগ্রি সেলসিয়াস।"
    marathi_voice = "mr-IN-AarohiNeural"

    corrected_voice, corrected_lang = VoiceCleaner.sanitize_voice_for_script(
        voice_name=marathi_voice,
        text=bengali_spoken_text,
        target_lang="mr",
    )

    assert corrected_voice == "bn-IN-TanishaaNeural"
    assert corrected_lang == "bn"


def test_pre_synthesis_script_check_marathi_intact():
    """Verify genuine Marathi text with Marathi voice is preserved intact."""
    marathi_spoken_text = "पुण्यात आज पाऊस पडण्याची शक्यता आहे।"
    marathi_voice = "mr-IN-AarohiNeural"

    voice, lang = VoiceCleaner.sanitize_voice_for_script(
        voice_name=marathi_voice,
        text=marathi_spoken_text,
        target_lang="mr",
    )

    assert voice == "mr-IN-AarohiNeural"
    assert lang == "mr"
