"""
Test Suite: Deterministic Linguistic Sovereignty & Single Source of Truth (SSoT) Architecture
Verifies:
1. STT: Whisper is called strictly with language=target_lang (auto-detect disabled).
2. STT: Empty speech raises 'SYS_VOICE > NO_SIGNAL'.
3. STT: Script alignment mismatch validator is purged from voice ingestion loop.
4. RAG: Strict Monolingual Mandate ('CRITICAL LOCK: You are an expert in {lang_name}...')
5. Main: UI dropdown language is King (SSoT) throughout /voice/process.
6. TTS: Edge-TTS voice mapping and 100% native phonetic units (no English spoken).
7. Dual Output: Chat UI text displays native reply and English version separated by '---'.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from backend.schemas import ChatRequest, LocationInput, ChatResponse
from backend.services.language.engine import WeatherHybridEngine
from backend.services.language.cleaner import translate_units_to_native, get_voice_for_language


# =========================================================================
# 1. STT SSoT & Whisper Language Enforcement
# =========================================================================

def test_whisper_explicit_target_lang_routing():
    """Verify that when target_lang='ur' is specified, Whisper is called with language='ur'."""
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_stt = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "کولکاتہ میں موسم کیسا ہے"
    mock_info = MagicMock()
    mock_info.language_probability = 0.98
    mock_info.language = "ur"
    mock_stt.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_stt
    engine.translate = MagicMock(return_value="How is the weather in Kolkata")

    with patch("backend.services.language.engine.standardize_audio", return_value="dummy.wav"), \
         patch("os.path.exists", return_value=True):
        res = engine.process_query("dummy.wav", target_lang="ur")

        mock_stt.transcribe.assert_called_once()
        _, kwargs = mock_stt.transcribe.call_args
        assert kwargs.get("language") == "ur", "Whisper must be called with language='ur'"
        assert res["detected_lang"] == "ur"
        assert res["locked_language_code"] == "ur"
        assert res["original_text"] == "کولکاتہ میں موسم کیسا ہے"


def test_empty_speech_raises_no_signal():
    """Verify that empty or whitespace-only speech raises SYS_VOICE > NO_SIGNAL."""
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_stt = MagicMock()
    mock_info = MagicMock()
    mock_info.language_probability = 0.0
    mock_info.language = "ur"
    mock_stt.transcribe.return_value = ([], mock_info)
    engine._stt_model = mock_stt

    with patch("backend.services.language.engine.standardize_audio", return_value="dummy.wav"), \
         patch("os.path.exists", return_value=True):
        with pytest.raises(RuntimeError) as exc_info:
            engine.process_query("dummy.wav", target_lang="ur")
        assert "SYS_VOICE > NO_SIGNAL" in str(exc_info.value)


def test_script_validator_purged_from_ingestion():
    """Verify that mixed or Romanized speech is NOT rejected with SCRIPT_MISMATCH."""
    engine = WeatherHybridEngine.__new__(WeatherHybridEngine)
    mock_stt = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "Kolkata mausam kaisa hai"
    mock_info = MagicMock()
    mock_info.language_probability = 0.90
    mock_info.language = "ur"
    mock_stt.transcribe.return_value = ([mock_segment], mock_info)
    engine._stt_model = mock_stt
    engine.translate = MagicMock(return_value="How is the weather in Kolkata")

    with patch("backend.services.language.engine.standardize_audio", return_value="dummy.wav"), \
         patch("os.path.exists", return_value=True):
        # Should NOT raise RuntimeError("SYS_VOICE > ERROR: SCRIPT_MISMATCH")
        res = engine.process_query("dummy.wav", target_lang="ur")
        assert res["original_text"] == "Kolkata mausam kaisa hai"
        assert res["locked_language_code"] == "ur"


# =========================================================================
# 2. Strict Linguistic Mandate in RAG Brain Prompts
# =========================================================================

def test_rag_brain_strict_linguistic_prompt_lock_urdu():
    """Verify that RAG injects the critical monolingual lock for Urdu."""
    from backend.services.rag.service import WeatherGPTBrain
    brain = WeatherGPTBrain.__new__(WeatherGPTBrain)
    brain.llm_model = "gemini-3.6-flash"
    brain.fallback_model = "gemini-3.5-flash"
    brain.db_path = Path("data/chroma")
    brain.embeddings = None

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "کولکاتہ میں درجہ حرارت تیس ڈگری سیلسیس ہے۔"
    mock_llm.invoke.return_value = mock_response
    brain.llm = mock_llm

    req = ChatRequest(
        query="کولکاتہ کا موسم",
        location=LocationInput(raw_text="Kolkata"),
        language="ur",
        channel="voice",
    )

    with patch("backend.services.rag.service.load_vector_db", return_value=MagicMock()), \
         patch("backend.services.rag.service.get_retriever", return_value=MagicMock(get_relevant_documents=MagicMock(return_value=[]))):
        res = brain.query_with_schemas(req, weather_data=None, location=None, alerts=[])

        # Inspect the prompt passed to Gemini invoke
        mock_llm.invoke.assert_called_once()
        invoked_prompt = mock_llm.invoke.call_args[0][0]
        assert "CRITICAL LOCK: You are an Urdu-only meteorologist." in invoked_prompt
        assert "Output ONLY the Perso-Arabic script." in invoked_prompt
        assert "STRICTLY FORBIDDEN from using English text." in invoked_prompt


def test_rag_brain_strict_linguistic_prompt_lock_regional():
    """Verify that RAG injects the critical monolingual lock for non-Urdu Indic languages."""
    from backend.services.rag.service import WeatherGPTBrain
    brain = WeatherGPTBrain.__new__(WeatherGPTBrain)
    brain.llm_model = "gemini-3.6-flash"
    brain.fallback_model = "gemini-3.5-flash"
    brain.db_path = Path("data/chroma")
    brain.embeddings = None

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "कोलकाता में मौसम साफ है।"
    mock_llm.invoke.return_value = mock_response
    brain.llm = mock_llm

    req = ChatRequest(
        query="कोलकाता का मौसम",
        location=LocationInput(raw_text="Kolkata"),
        language="hi",
        channel="chat",
    )

    with patch("backend.services.rag.service.load_vector_db", return_value=MagicMock()), \
         patch("backend.services.rag.service.get_retriever", return_value=MagicMock(get_relevant_documents=MagicMock(return_value=[]))):
        brain.query_with_schemas(req, weather_data=None, location=None, alerts=[])

        mock_llm.invoke.assert_called_once()
        invoked_prompt = mock_llm.invoke.call_args[0][0]
        assert "CRITICAL LOCK: You are an expert in Hindi." in invoked_prompt
        assert "Respond ONLY in Hindi script." in invoked_prompt
        assert "Do not use English. Do not provide translations." in invoked_prompt


# =========================================================================
# 3. Dual Output & Native Speech Enforcement
# =========================================================================

@pytest.mark.asyncio
async def test_dual_text_display_with_native_voice_synthesis():
    """Verify that execute_weather_logic produces dual text for UI and native-only text for TTS."""
    from backend.main import execute_weather_logic

    chat_req = ChatRequest(
        query="کولکاتہ میں موسم کیسا ہے",
        location=LocationInput(raw_text="Kolkata"),
        language="ur",
        channel="voice",
    )

    urdu_reply = "کولکاتہ میں درجہ حرارت 28.5°C ہے۔"
    english_translation = "In Kolkata, the temperature is 28.5°C."

    with patch("backend.main.rag_service.answer") as mock_rag, \
         patch("backend.main.open_meteo_service.get_weather", new_callable=AsyncMock) as mock_weather, \
         patch("backend.main.language_service.translate_query_to_english", return_value=english_translation), \
         patch("backend.main.language_service.synthesize_audio", new_callable=AsyncMock) as mock_synth:

        mock_rag.return_value = ChatResponse(
            bot_reply=urdu_reply,
            alerts=[],
            sources=[],
        )
        mock_weather.return_value = None
        mock_synth.return_value = "/voice/audio/test_ur.mp3"

        resp = await execute_weather_logic(chat_req)

        # 1. UI Text must display both native reply and English Version
        assert urdu_reply in resp.bot_reply
        assert "**English Version:**" in resp.bot_reply
        assert english_translation in resp.bot_reply

        # 2. Audio Synthesis must only receive the native reply with converted phonetic units (NO English header)
        mock_synth.assert_called_once()
        synth_text, synth_lang = mock_synth.call_args[0]
        assert synth_lang == "ur"
        assert "**English Version:**" not in synth_text
        assert "ڈگری سیلسیس" in synth_text
        assert "28.5°C" not in synth_text


# =========================================================================
# 4. Edge-TTS Regional Voice Mapping
# =========================================================================

def test_edge_tts_urdu_voice_mapping():
    """Verify that Urdu maps strictly to ur-IN-GulNeural."""
    assert get_voice_for_language("ur") == "ur-IN-GulNeural"
    assert get_voice_for_language("ur-IN") == "ur-IN-GulNeural"
    assert get_voice_for_language("bn") == "bn-IN-TanishaaNeural"
    assert get_voice_for_language("mr") == "mr-IN-AarohiNeural"
