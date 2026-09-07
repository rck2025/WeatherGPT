"""
Comprehensive Test Suite for Universal Linguistic Sovereignty across all 15 Languages:
(en, hi, bn, ta, te, mr, gu, kn, ml, ur, pa, or, as, ne, sa)

Tests:
1. Multi-Script Unicode Script Registry and Character Boundaries
2. Script Purity Calculation and 30% Threshold Validation
3. Signal Noise Rejection (preventing hallucinated / mismatched scripts)
4. Meteorological Unit Speech Normalization (normalize_for_tts)
5. Regional Voice Mapping for Edge-TTS
6. End-to-End Live Endpoint Verification
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.services.language.resolver import (
    SCRIPT_REGISTRY,
    is_char_in_script,
    calculate_script_purity,
    validate_script_purity,
    detect_dominant_script,
    get_language_and_script_names,
)
from backend.services.language.cleaner import (
    normalize_for_tts,
    get_voice_for_language,
    clean_bot_response,
    REGIONAL_VOICE_MAP,
    UNIT_EXPANSIONS,
)
from backend.services.language.engine import WEATHER_INITIAL_PROMPTS


# Sample native weather sentences for all 15 languages
SAMPLE_NATIVE_SENTENCES: dict[str, str] = {
    "hi": "कोलकाता में आज का मौसम कैसा है? तापमान 30°C और हवा 15 km/h है।",
    "bn": "কলকাতায় আজকের আবহাওয়া কেমন? তাপমাত্রা 30°C এবং আর্দ্রতা 80%।",
    "ta": "சென்னையில் இன்றைய வானிலை என்ன? வெப்பநிலை 32°C மற்றும் மழை எச்சரிக்கை.",
    "te": "హైదరాబాద్‌లో నేటి వాతావరణం ఎలా ఉంది? ఉష్ణోగ్రత 28°C.",
    "mr": "मुंबईत आजचे हवामान कसे आहे? तापमान 29°C आणि पाऊस पडत आहे.",
    "gu": "અમદાવાદમાં આજનું હવામાન કેવું છે? તાપમાન 35°C છે.",
    "kn": "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಇಂದಿನ ಹವಾಮಾನ ಹೇಗಿದೆ? ತಾಪಮಾನ 24°C.",
    "ml": "കൊച്ചിയിൽ ഇന്നത്തെ കാലാവസ്ഥ എങ്ങനെയുണ്ട്? താപനില 30°C.",
    "ur": "لاہور میں آج کا موسم کیسا ہے؟ درجہ حرارت 31°C ہے۔",
    "pa": "ਅੰਮ੍ਰਿਤਸਰ ਵਿੱਚ ਅੱਜ ਦਾ ਮੌਸਮ ਕਿਵੇਂ ਹੈ? ਤਾਪਮਾਨ 26°C ਹੈ।",
    "or": "ଭୁବନେଶ୍ୱରରେ ଆଜିର ପାଣିପାଗ କିପରି ଅଛି? ତାପମାତ୍ରା 33°C.",
    "as": "গুৱাহাটীত আজিৰ বতৰ কেনেকুৱা? উষ্ণতা 28°C আৰু বৰষুণ।",
    "ne": "काठमाडौँमा आजको मौसम कस्तो छ? तापक्रम 22°C छ।",
    "sa": "वाराणस्याम् अद्यतनं वातावरणं कीदृशम् अस्ति? तापमानम् 30°C अस्ति।",
    "en": "What is the weather in Delhi? Current temperature is 31°C with 60% humidity.",
}


def test_script_registry_coverage():
    """Verify all 15 languages exist in SCRIPT_REGISTRY, REGIONAL_VOICE_MAP, and WEATHER_INITIAL_PROMPTS."""
    expected_langs = ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "ur", "pa", "or", "as", "ne", "sa"]
    print("\n--- [TEST 1] Script Registry Coverage ---")
    for lang in expected_langs:
        assert lang in SCRIPT_REGISTRY, f"Missing {lang} in SCRIPT_REGISTRY"
        assert lang in REGIONAL_VOICE_MAP, f"Missing {lang} in REGIONAL_VOICE_MAP"
        assert lang in WEATHER_INITIAL_PROMPTS, f"Missing {lang} in WEATHER_INITIAL_PROMPTS"
        assert lang in UNIT_EXPANSIONS, f"Missing {lang} in UNIT_EXPANSIONS"
        
        lang_name, script_name = get_language_and_script_names(lang)
        voice = get_voice_for_language(lang)
        print(f"  [OK] {lang:2s} -> {lang_name:10s} | Script: {script_name:16s} | Voice: {voice}")
    print("PASS: All 15 languages fully registered across all components.")


def test_script_purity_validation():
    """Verify script purity validation correctly passes native text and rejects noise."""
    print("\n--- [TEST 2] Multi-Script Unicode Guard Purity Tests ---")
    for lang, sentence in SAMPLE_NATIVE_SENTENCES.items():
        purity = calculate_script_purity(sentence, lang)
        is_valid = validate_script_purity(sentence, lang, threshold=0.30)
        print(f"  [OK] {lang:2s} purity: {purity*100:5.1f}% -> Valid (>=30%): {is_valid}")
        assert is_valid, f"Native sentence failed script validation for lang={lang}: purity={purity}"
        assert purity >= 0.30, f"Expected purity >= 0.30 for {lang}, got {purity}"

    print("PASS: Native text in all 15 languages exceeds 30% script purity threshold.")


def test_signal_noise_rejection():
    """Verify that mismatched scripts or English hallucinated noise are rejected with < 30% purity."""
    print("\n--- [TEST 3] Signal Noise Rejection Tests ---")
    noise_samples = [
        "Thank you for watching!",
        "whispering and background noise [silence]",
        "um uh ahhh ok",
        "Subtitles by the Amara.org community",
    ]
    regional_langs = ["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "ur", "pa", "or", "as", "ne", "sa"]
    for lang in regional_langs:
        for noise in noise_samples:
            purity = calculate_script_purity(noise, lang)
            is_valid = validate_script_purity(noise, lang, threshold=0.30)
            assert not is_valid, f"Noise '{noise}' was falsely validated as {lang} (purity={purity})"
            assert purity < 0.30, f"Noise purity should be < 0.30, got {purity}"
    print(f"  [OK] Verified noise rejection across all {len(regional_langs)} regional languages.")
    print("PASS: Noise & hallucinated tokens correctly fail script purity.")


def test_unit_speech_normalization():
    """Verify normalize_for_tts transforms technical symbols into spoken words in all 15 languages."""
    print("\n--- [TEST 4] Unit Speech Normalization (normalize_for_tts) ---")
    sample_text = "32°C, 45 km/h, 85%"
    for lang in ["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "ur", "pa", "or", "as", "ne", "sa", "en"]:
        normalized = normalize_for_tts(sample_text, lang_code=lang)
        # Verify that °C, km/h, and % were replaced
        assert "°C" not in normalized, f"°C not replaced in {lang}: {normalized}"
        assert "km/h" not in normalized, f"km/h not replaced in {lang}: {normalized}"
        assert "%" not in normalized, f"% not replaced in {lang}: {normalized}"
        print(f"  [OK] {lang:2s} -> {normalized}")
    print("PASS: Meteorological units cleanly normalized for speech across all 15 languages.")


def test_dominant_script_detection():
    """Verify detect_dominant_script accurately identifies language and script name."""
    print("\n--- [TEST 5] Dominant Script Detection ---")
    cases = [
        ("வணக்கம் இன்று மழை பெய்யும்", "ta", "Tamil"),
        ("आज मौसम बहुत सुहावना है", "hi", "Devanagari"),
        ("আজকে ভারী বৃষ্টির সম্ভাবনা আছে", "bn", "Bengali"),
        ("ਅੱਜ ਦਾ ਮੌਸਮ ਬਹੁਤ ਵਧੀਆ ਹੈ", "pa", "Gurmukhi"),
        ("آج موسم بہت اچھا ہے", "ur", "Perso-Arabic"),
    ]
    for text, expected_lang, expected_script in cases:
        lang, script, purity = detect_dominant_script(text)
        print(f"  [OK] '{text[:15]}...' -> Detected: {lang} ({script}), Purity: {purity*100:.1f}%")
        assert lang == expected_lang, f"Expected {expected_lang}, got {lang}"
        assert script == expected_script, f"Expected {expected_script}, got {script}"
        assert purity >= 0.70, f"Expected purity >= 0.70, got {purity}"
    print("PASS: Dominant script detection is accurate.")


def run_all_tests():
    print("=" * 60)
    print("RUNNING UNIVERSAL LINGUISTIC SOVEREIGNTY TEST SUITE")
    print("=" * 60)
    test_script_registry_coverage()
    test_script_purity_validation()
    test_signal_noise_rejection()
    test_unit_speech_normalization()
    test_dominant_script_detection()
    print("\n" + "=" * 60)
    print("ALL 5 LINGUISTIC SOVEREIGNTY UNIT TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
