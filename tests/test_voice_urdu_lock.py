"""Test Suite for Strict Urdu Script-Lock, Voice Enforcement & Unit Translation."""

from backend.services.language.cleaner import (
    translate_units_to_native,
    get_voice_for_language,
    VoiceCleaner,
)


def test_translate_units_to_native_urdu():
    """Verify that '27.9°C' is converted to 'ستائیس اعشاریہ نو ڈگری سیلسیس'."""
    text = "Kolkata temperature is 27.9°C."
    result = translate_units_to_native(text, lang="ur")
    assert "ستائیس اعشاریہ نو ڈگری سیلسیس" in result, f"Expected Urdu converted units, got: {result}"


def test_translate_units_to_native_wind_and_humidity():
    """Verify wind speed and humidity unit translation for Urdu."""
    text = "Wind speed 25 km/h with 65% humidity."
    result = translate_units_to_native(text, lang="ur")
    assert "پچیس کلومیٹر فی گھنٹہ" in result
    assert "پینسٹھ فیصد" in result


def test_get_voice_for_urdu():
    """Verify that 'ur' maps strictly to 'ur-IN-GulNeural'."""
    voice = get_voice_for_language("ur")
    assert voice == "ur-IN-GulNeural"


def test_voice_cleaner_perso_arabic_detection():
    """Verify VoiceCleaner detects Perso-Arabic text and enforces ur-IN-GulNeural."""
    urdu_text = "کولکاتہ میں آج درجہ حرارت ستائیس اعشاریہ نو ڈگری سیلسیس رہے گا۔"
    script = VoiceCleaner.detect_script(urdu_text)
    assert script == "ur"

    voice, lang = VoiceCleaner.sanitize_voice_for_script("en-IN-NeerjaExpressiveNeural", urdu_text, "ur")
    assert voice == "ur-IN-GulNeural"
    assert lang == "ur"


def test_voice_process_ssot_urdu():
    """Verify that voice endpoint locks target_lang to Urdu when UI specifies user_language='ur'."""
    from backend.services.voice.engine import process_query
    from unittest.mock import patch, MagicMock

    with patch("backend.services.voice.engine.language_service.transcribe_audio") as mock_stt:
        mock_stt.return_value = {
            "original_text": "کولکاتہ میں موسم",
            "detected_lang": "ur",
            "confidence": 0.98,
            "english_query": "Weather in Kolkata",
            "transcription_method": "Whisper",
            "locked_language_code": "ur",
        }
        res = process_query("dummy.wav", target_lang="ur")
        mock_stt.assert_called_once_with(
            "dummy.wav",
            target_lang="ur",
            language_hint="ur",
            user_language="ur",
        )
        assert res["locked_language_code"] == "ur"
        assert res["detected_lang"] == "ur"


if __name__ == "__main__":
    test_translate_units_to_native_urdu()
    print("PASS: test_translate_units_to_native_urdu")
    test_translate_units_to_native_wind_and_humidity()
    print("PASS: test_translate_units_to_native_wind_and_humidity")
    test_get_voice_for_urdu()
    print("PASS: test_get_voice_for_urdu")
    test_voice_cleaner_perso_arabic_detection()
    print("PASS: test_voice_cleaner_perso_arabic_detection")
    test_voice_process_ssot_urdu()
    print("PASS: test_voice_process_ssot_urdu")
    print("\nALL URDU VOICE & UNIT TESTS PASSED!")
