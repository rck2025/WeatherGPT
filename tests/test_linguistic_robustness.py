"""
Test Suite: Linguistic Robustness, Universal Indian Script Normalizer,
Whisper Nudge / Multi-Stage LID, and Phonetic Fallbacks.
"""

import pytest
from backend.services.language.resolver import (
    validate_script_alignment,
    detect_dominant_script,
    detect_script_language,
    SCRIPT_FAMILIES,
    SCRIPT_REGISTRY,
)
from backend.services.language.cleaner import (
    clean_transcribed_input,
    get_voice_for_language,
    get_phonetic_fallback_voice,
    REGIONAL_VOICE_MAP,
    PHONETIC_FALLBACK_MAP,
)


def test_universal_devanagari_marathi_validation():
    """Verify Marathi queries in Devanagari pass without SCRIPT_MISMATCH."""
    marathi_text = "पुण्यात उद्या पाऊस पडेल का?"
    # Both mr and hi share Devanagari script family
    is_valid, _ = validate_script_alignment(marathi_text, "mr")
    assert is_valid is True
    is_valid, _ = validate_script_alignment(marathi_text, "hi")
    assert is_valid is True
    is_valid, _ = validate_script_alignment(marathi_text, "kok")
    assert is_valid is True
    is_valid, _ = validate_script_alignment(marathi_text, "sa")
    assert is_valid is True
    is_valid, _ = validate_script_alignment(marathi_text, "ne")
    assert is_valid is True


def test_strict_cjk_rejection():
    """Verify CJK hallucination text is rejected with SCRIPT_MISMATCH."""
    cjk_chinese = "今天天气很好，请问下雨吗？"
    cjk_japanese = "明日の天気はどうですか？"
    cjk_korean = "내일 날씨가 어떻습니까?"

    is_valid1, reason1 = validate_script_alignment(cjk_chinese, "mr")
    assert is_valid1 is False
    assert "SCRIPT_MISMATCH" in reason1

    is_valid2, reason2 = validate_script_alignment(cjk_japanese, "hi")
    assert is_valid2 is False
    assert "SCRIPT_MISMATCH" in reason2

    is_valid3, reason3 = validate_script_alignment(cjk_korean, "bn")
    assert is_valid3 is False
    assert "SCRIPT_MISMATCH" in reason3


def test_input_denoising_preprocessor():
    """Verify cleaner removes fillers and non-lexical acoustic markers."""
    dirty_input = "[breathing] Uh, um, पुण्यात आज पाऊस पडेल का? (sigh) अह..."
    cleaned = clean_transcribed_input(dirty_input)
    assert "[breathing]" not in cleaned
    assert "(sigh)" not in cleaned
    assert "Uh" not in cleaned
    assert "um" not in cleaned
    assert "अह" not in cleaned
    assert "पुण्यात आज पाऊस पडेल का?" in cleaned


def test_all_22_scheduled_languages_voice_mapping():
    """Verify all 22 Eighth Schedule languages have voice mappings and never fall back to English."""
    scheduled_22 = [
        "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
        "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur"
    ]

    for lang in scheduled_22:
        voice = get_voice_for_language(lang)
        assert voice is not None, f"Missing voice mapping for {lang}"
        # Regional languages must NEVER fall back to English voices
        assert not voice.startswith("en-"), f"Regional language {lang} fell back to English voice: {voice}"


def test_phonetic_fallbacks_for_unsupported_voices():
    """Verify languages without native Edge-TTS neural voices fall back to phonetic siblings."""
    # Konkani -> Marathi voice
    assert get_voice_for_language("kok") == "mr-IN-AarohiNeural"
    # Assamese -> Bengali voice
    assert get_voice_for_language("as") == "bn-IN-TanishaaNeural"
    # Odia -> Hindi voice
    assert get_voice_for_language("or") == "hi-IN-SwaraNeural"
    # Punjabi -> native voice or fallback
    assert get_voice_for_language("pa") == "pa-IN-OjasNeural"
    assert get_phonetic_fallback_voice("pa") == "hi-IN-SwaraNeural"
    # Kashmiri -> Urdu voice
    assert get_voice_for_language("ks") == "ur-IN-GulNeural"
    # Sindhi -> Urdu voice
    assert get_voice_for_language("sd") == "ur-IN-GulNeural"
    # Bodo -> Hindi voice
    assert get_voice_for_language("brx") == "hi-IN-SwaraNeural"
    # Dogri -> Hindi voice
    assert get_voice_for_language("doi") == "hi-IN-SwaraNeural"
    # Maithili -> Hindi voice
    assert get_voice_for_language("mai") == "hi-IN-SwaraNeural"
    # Santali -> Hindi voice
    assert get_voice_for_language("sat") == "hi-IN-SwaraNeural"
    # Manipuri -> Bengali voice
    assert get_voice_for_language("mni") == "bn-IN-TanishaaNeural"


def test_marathi_vs_hindi_lexical_disambiguation():
    """Verify multi-stage LID accurately disambiguates Marathi from Hindi in Devanagari."""
    marathi_query = "पुण्यात आज हवामान कसे आहे?"
    hindi_query = "पुणे में आज मौसम कैसा है?"

    # Marathi detection
    lang_mr, _, _ = detect_dominant_script(marathi_query)
    assert lang_mr == "mr", f"Expected mr, got {lang_mr}"

    # Hindi detection
    lang_hi, _, _ = detect_dominant_script(hindi_query)
    assert lang_hi == "hi", f"Expected hi, got {lang_hi}"

    # High-level detect_script_language
    assert detect_script_language(marathi_query) == "mr"
    assert detect_script_language(hindi_query) == "hi"


def test_cross_script_purity():
    """Verify scripts from different families reject each other."""
    tamil_text = "சென்னையில் இன்று மழை பெய்யுமா?"
    telugu_text = "హైదరాబాద్‌లో ఈరోజు వాతావరణం ఎలా ఉంది?"

    is_valid_ta, _ = validate_script_alignment(tamil_text, "ta")
    assert is_valid_ta is True

    is_valid_te, _ = validate_script_alignment(telugu_text, "te")
    assert is_valid_te is True

    # Tamil script with Telugu expected throws SCRIPT_MISMATCH
    is_mismatched, reason = validate_script_alignment(tamil_text, "te")
    assert is_mismatched is False
    assert "SCRIPT_MISMATCH" in reason
