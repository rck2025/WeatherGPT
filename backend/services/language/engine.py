"""
WeatherHybridEngine — core voice processing engine.

Combines:
  - FFmpeg audio standardisation (format-agnostic ingestion)
  - Faster-Whisper (offline CPU STT + language detection)
  - Bhashini API translation with deep-translator fallback
  - Microsoft Edge-TTS neural speech synthesis for 10 Indian regional languages

Sourced and adapted from SOHAM-DEV2/WeatherGPT-MK1 (feature/voice-integrated-v1).
"""
import logging
import os
import subprocess

import requests

from backend.services.language.cleaner import (
    clean_bot_response,
    expand_units_for_language,
    get_voice_for_language,
    safe_translate,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Audio standardiser (format-agnostic ingestion)
# -----------------------------------------------------------------------

def standardize_audio(input_path: str, output_path: str | None = None) -> str:
    """
    Convert any browser audio blob (webm, ogg, m4a, mp3, wav) to a
    Whisper-optimised 16 kHz Mono WAV file using FFmpeg.

    If FFmpeg is unavailable the original path is returned so that Whisper
    can still attempt to process the file (graceful degradation).
    """
    if not os.path.exists(input_path):
        return input_path

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_resampled.wav"

    command = [
        "ffmpeg", "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        output_path, "-y",
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, check=True)
        return output_path
    except FileNotFoundError:
        logger.warning("FFmpeg not found; using original audio file without resampling.")
        return input_path
    except subprocess.CalledProcessError as exc:
        logger.warning("Audio conversion failed (%s); using original file.", exc)
        return input_path


# -----------------------------------------------------------------------
# Hybrid Voice Engine
# -----------------------------------------------------------------------

class WeatherHybridEngine:
    """
    Unified voice engine for WeatherGPT:

    - Format-agnostic audio ingestion (16 kHz Mono WAV via FFmpeg)
    - Fast offline STT with Faster-Whisper (int8 CPU)
    - Hybrid translation: Bhashini Cloud → deep-translator fallback
    - Full LLM-output de-noising (markdown, emojis, units, filler)
    - High-clarity neural TTS for all major Indian regional languages
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        logger.info("Initialising WeatherHybridEngine (%s on %s)…", model_size, device)

        # Lazy import so the server starts fast even when faster-whisper isn't installed yet
        try:
            from faster_whisper import WhisperModel  # type: ignore
            self._stt_model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except ImportError:
            logger.warning("faster-whisper not installed; STT transcription will be unavailable.")
            self._stt_model = None

        # Bhashini credentials (optional — falls back to deep-translator automatically)
        self._bhashini_user_id = os.getenv("BHASHINI_USER_ID")
        self._bhashini_api_key = os.getenv("BHASHINI_API_KEY")
        self._bhashini_url = os.getenv(
            "BHASHINI_URL",
            "https://meity-auth.ulcacontrib.org/ulca/gw/v1/decode/pipeline",
        )

    # ------------------------------------------------------------------
    # Public: STT
    # ------------------------------------------------------------------

    def process_query(self, audio_path: str, language_hint: str | None = None) -> dict:
        """
        1. Standardise incoming audio to 16 kHz Mono WAV.
        2. Transcribe with Faster-Whisper (using language_hint if provided, or auto-detecting).
        3. Translate regional query to English for LLM/RAG consumption.

        Returns:
            {
                "original_text": str,
                "detected_lang": str,   # ISO 639-1 code e.g. "hi", "bn"
                "confidence":    float,
                "english_query": str,
            }
        """
        if self._stt_model is None:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: .venv/bin/pip install faster-whisper"
            )
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path!r}")

        optimised = standardize_audio(audio_path)
        logger.debug("Whisper: transcribing %s (hint=%s)…", optimised, language_hint)

        # Initialise before try so they are always defined if an exception fires
        user_text = ""
        user_lang = language_hint if (language_hint and language_hint != "en") else "en"
        info = None

        try:
            transcribe_kwargs = {"beam_size": 5}
            if language_hint and language_hint != "en":
                transcribe_kwargs["language"] = language_hint

            segments, info = self._stt_model.transcribe(optimised, **transcribe_kwargs)
            user_text = " ".join(s.text for s in segments).strip()
            user_lang = language_hint if (language_hint and language_hint != "en") else (info.language.lower() if info.language else "en")
        finally:
            # Always clean up the resampled temp file to avoid disk accumulation
            if optimised != audio_path and os.path.exists(optimised):
                try:
                    os.remove(optimised)
                except OSError:
                    pass

        if not user_text:
            raise RuntimeError("Whisper returned an empty transcription.")

        confidence = info.language_probability if info else 0.0
        logger.info("STT: %r (lang=%s, conf=%.1f%%)", user_text, user_lang.upper(), confidence * 100)

        english_text = self.translate(user_text, source_lang=user_lang, target_lang="en")

        # Whisper base often transliterates regional languages into Latin script.
        # To get the native script, we translate the English query back to the regional language.
        native_text = user_text
        if user_lang != "en":
            native_text = self.translate(english_text, source_lang="en", target_lang=user_lang)

        return {
            "original_text": native_text,
            "detected_lang": user_lang,
            "confidence":    info.language_probability,
            "english_query": english_text,
        }

    # ------------------------------------------------------------------
    # Public: Translation
    # ------------------------------------------------------------------

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate *text* from *source_lang* to *target_lang*.
        Tries Bhashini first (if credentials are configured), then falls
        back to the deep-translator multi-engine chain.
        """
        if not text:
            return text

        src = source_lang.split("-")[0].lower()
        tgt = target_lang.split("-")[0].lower()

        if src == tgt:
            return text

        if self._bhashini_user_id and self._bhashini_api_key:
            try:
                result = self._bhashini_translate(text, src, tgt)
                if result and result != text:
                    return result
            except Exception as exc:
                logger.debug("Bhashini skipped: %s", exc)

        return safe_translate(text, source_lang=src, target_lang=tgt)

    # ------------------------------------------------------------------
    # Public: TTS
    # ------------------------------------------------------------------

    async def generate_regional_response(
        self,
        raw_response: str,
        target_lang: str = "hi",
        output_file: str = "weather_response.mp3",
        source_is_english: bool = True,
    ) -> dict:
        """
        End-to-end voice synthesis pipeline:
        1. Strip LLM noise (markdown, thinking tags, emojis, filler).
        2. Translate clean English text into the target regional language.
        3. Expand meteorological units into natural spoken regional words.
        4. Synthesise neural audio with Microsoft Edge-TTS.

        Returns:
            {
                "cleaned_english":   str,
                "final_spoken_text": str,
                "language":          str,
                "voice_used":        str,
                "output_file":       str,
            }
        """
        try:
            import edge_tts  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed. Run: .venv/bin/pip install edge-tts"
            ) from exc

        norm_lang = target_lang.split("-")[0].lower() if target_lang else "hi"

        # Step 1 — clean raw English LLM output
        cleaned_en = clean_bot_response(raw_response, lang_code="en")

        # Step 2 — translate to target regional language
        if norm_lang != "en" and source_is_english:
            regional_text = self.translate(cleaned_en, source_lang="en", target_lang=norm_lang)
        else:
            regional_text = cleaned_en

        # Step 3 — regional speech polish (unit expansion + spacing)
        final_spoken = clean_bot_response(regional_text, lang_code=norm_lang)

        # Step 4 — pick neural voice and synthesise
        voice_name = get_voice_for_language(norm_lang)
        communicate = edge_tts.Communicate(final_spoken, voice_name)
        await communicate.save(output_file)

        return {
            "cleaned_english":   cleaned_en,
            "final_spoken_text": final_spoken,
            "language":          norm_lang,
            "voice_used":        voice_name,
            "output_file":       output_file,
        }

    # ------------------------------------------------------------------
    # Private: Bhashini helper
    # ------------------------------------------------------------------

    def _bhashini_translate(self, text: str, source: str, target: str) -> str:
        payload = {
            "pipelineTasks": [{
                "taskType": "translation",
                "config": {"language": {"sourceLanguage": source, "targetLanguage": target}},
            }],
            "inputData": {"input": [{"source": text}]},
        }
        headers = {
            "Content-Type": "application/json",
            "userID":        self._bhashini_user_id,
            "ulcaApiKey":    self._bhashini_api_key,
        }
        response = requests.post(self._bhashini_url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()["pipelineResponse"][0]["output"][0]["target"]
        return text
