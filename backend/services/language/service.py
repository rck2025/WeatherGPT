"""
LanguageService — the adapter that main.py calls.

This is the only public interface exposed to the rest of the backend.
It wraps WeatherHybridEngine with lazy initialisation and a clean,
contract-safe API that conforms to the frozen ChatRequest / ChatResponse
schema:

  ChatRequest.language  →  target output language
  ChatRequest.channel   →  "voice" triggers audio synthesis
  ChatResponse.bot_reply  ←  translated regional text
  ChatResponse.audio_url  ←  URL to temporary MP3 file (or None)
"""
import base64
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path

from backend.services.language.cleaner import (
    REGIONAL_VOICE_MAP,
    clean_bot_response,
    safe_translate,
)

logger = logging.getLogger(__name__)

# Temporary audio files are stored here and auto-deleted after TTL seconds
_AUDIO_DIR = Path(__file__).resolve().parent / "audio_tmp"
_AUDIO_DIR.mkdir(exist_ok=True)

# Auto-delete generated audio files after this many seconds
_AUDIO_TTL_SECONDS = 120


def _delete_after(path: str, delay: int) -> None:
    """Background thread: delete *path* after *delay* seconds."""
    def _worker():
        time.sleep(delay)
        try:
            os.remove(path)
        except OSError:
            pass
    threading.Thread(target=_worker, daemon=True).start()


class LanguageService:
    """
    High-level language and voice service for WeatherGPT.

    Provides three capabilities to main.py:
      1. translate_query_to_english()  — pre-step before RAG
      2. process_bot_reply()           — post-step: translate reply to regional language
      3. synthesize_audio()            — optional: generate MP3, return URL

    Also exposes get_supported_languages() and the engine instance for the
    /voice/* FastAPI router.
    """

    # Supported languages metadata (used by GET /voice/languages) - 22 Scheduled Indian Languages + English
    SUPPORTED_LANGUAGES: list[dict] = [
        {"code": "en",  "name": "Indian English", "voice": "en-IN-NeerjaExpressiveNeural", "gender": "Female"},
        {"code": "hi",  "name": "Hindi",          "voice": "hi-IN-SwaraNeural",            "gender": "Female"},
        {"code": "bn",  "name": "Bengali",        "voice": "bn-IN-TanishaaNeural",         "gender": "Female"},
        {"code": "mr",  "name": "Marathi",        "voice": "mr-IN-AarohiNeural",           "gender": "Female"},
        {"code": "te",  "name": "Telugu",         "voice": "te-IN-ShrutiNeural",           "gender": "Female"},
        {"code": "ta",  "name": "Tamil",          "voice": "ta-IN-PallaviNeural",          "gender": "Female"},
        {"code": "gu",  "name": "Gujarati",       "voice": "gu-IN-DhwaniNeural",           "gender": "Female"},
        {"code": "ur",  "name": "Urdu",           "voice": "ur-IN-GulNeural",              "gender": "Female"},
        {"code": "kn",  "name": "Kannada",        "voice": "kn-IN-SapnaNeural",            "gender": "Female"},
        {"code": "or",  "name": "Odia",           "voice": "hi-IN-SwaraNeural",            "gender": "Female"},
        {"code": "ml",  "name": "Malayalam",      "voice": "ml-IN-SobhanaNeural",          "gender": "Female"},
        {"code": "pa",  "name": "Punjabi",        "voice": "pa-IN-OjasNeural",             "gender": "Male"},
        {"code": "as",  "name": "Assamese",       "voice": "bn-IN-TanishaaNeural",         "gender": "Female"},
        {"code": "mai", "name": "Maithili",        "voice": "hi-IN-SwaraNeural",            "gender": "Female"},
        {"code": "sat", "name": "Santali",         "voice": "hi-IN-SwaraNeural",            "gender": "Female"},
        {"code": "ks",  "name": "Kashmiri",        "voice": "ur-IN-GulNeural",              "gender": "Female"},
        {"code": "ne",  "name": "Nepali",          "voice": "ne-NP-HemkalaNeural",          "gender": "Female"},
        {"code": "kok", "name": "Konkani",         "voice": "mr-IN-AarohiNeural",           "gender": "Female"},
        {"code": "sd",  "name": "Sindhi",          "voice": "ur-IN-GulNeural",              "gender": "Female"},
        {"code": "doi", "name": "Dogri",           "voice": "hi-IN-SwaraNeural",            "gender": "Female"},
        {"code": "mni", "name": "Manipuri",        "voice": "bn-IN-TanishaaNeural",         "gender": "Female"},
        {"code": "brx", "name": "Bodo",            "voice": "hi-IN-SwaraNeural",            "gender": "Female"},
        {"code": "sa",  "name": "Sanskrit",        "voice": "hi-IN-SwaraNeural",            "gender": "Female"},
    ]

    def __init__(self) -> None:
        self._engine = None
        self._engine_lock = threading.Lock()

    @property
    def engine(self):
        """Lazy-initialise WeatherHybridEngine on first use."""
        if self._engine is None:
            with self._engine_lock:
                if self._engine is None:
                    from backend.services.language.engine import WeatherHybridEngine
                    self._engine = WeatherHybridEngine(
                        model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
                        device=os.getenv("WHISPER_DEVICE", "cpu"),
                        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
                    )
        return self._engine

    # ------------------------------------------------------------------
    # 1. Pre-step: translate regional user query → English for RAG
    # ------------------------------------------------------------------

    def translate_query_to_english(self, text: str, source_lang: str) -> str:
        """
        Translate a regional-language user query into English so that
        location resolution and RAG vector search work reliably.

        Uses Bhashini Tier-1 Gateway with deep_translator fallback.
        """
        if not text or source_lang == "en":
            return text
        try:
            from backend.services.language.translator import translate_text
            return translate_text(text, source_lang=source_lang, target_lang="en")
        except Exception:
            logger.exception("Query translation to English failed; using original text.")
            return text

    # ------------------------------------------------------------------
    # 2. Post-step: translate + de-noise bot reply → regional language
    # ------------------------------------------------------------------

    def process_bot_reply(self, bot_reply: str, target_lang: str) -> str:
        """
        Translate the English bot reply into the user's target regional language
        while preserving all Markdown formatting (headers, bolding, bullet points, linebreaks).

        Uses Bhashini Tier-1 Gateway with deep_translator fallback.
        """
        if not bot_reply or target_lang == "en":
            return bot_reply
        try:
            from backend.services.language.translator import translate_text
            # Strip internal thinking tags if present but preserve full Markdown structure
            clean_input = re.sub(r"<\s*think\s*>[\s\S]*?<\s*/\s*think\s*>", "", bot_reply, flags=re.IGNORECASE).strip()
            return translate_text(clean_input, source_lang="en", target_lang=target_lang)
        except Exception:
            logger.exception("bot_reply translation failed; returning original English reply.")
            return bot_reply

    # ------------------------------------------------------------------
    # 3. Optional: synthesize audio → return audio_url
    # ------------------------------------------------------------------

    async def synthesize_audio(self, text: str, target_lang: str) -> str | None:
        """
        Synthesise *text* (already translated into *target_lang*) as a
        neural MP3 audio file using Microsoft Edge-TTS.

        Returns:
            A relative URL string  e.g.  "/voice/audio/<filename>.mp3"
            that maps to the static file served by the router, or
            None if synthesis fails (graceful degradation).
        """
        filename = f"response_{uuid.uuid4().hex}_{target_lang}.mp3"
        output_path = str(_AUDIO_DIR / filename)
        try:
            result = await self.engine.generate_regional_response(
                raw_response=text,
                target_lang=target_lang,
                output_file=output_path,
                source_is_english=False,   # text is already translated
            )
            _delete_after(result["output_file"], _AUDIO_TTL_SECONDS)
            return f"/voice/audio/{filename}"
        except Exception:
            logger.exception("Audio synthesis failed; audio_url will be None.")
            return None

    # ------------------------------------------------------------------
    # 4. Transcribe audio blob (used by /voice/transcribe endpoint)
    # ------------------------------------------------------------------

    def transcribe_audio(
        self,
        audio_path: str,
        target_lang: str | None = None,
        language_hint: str | None = None,
        user_language: str | None = None,
    ) -> dict:
        """
        Run Faster-Whisper STT on *audio_path* and return transcription metadata.
        Delegates to WeatherHybridEngine.process_query() with target_lang SSoT.
        """
        return self.engine.process_query(
            audio_path,
            target_lang=target_lang,
            language_hint=language_hint,
            user_language=user_language,
        )

    # ------------------------------------------------------------------
    # 5. Synthesize JSON (used by /voice/synthesize-json endpoint)
    # ------------------------------------------------------------------

    async def synthesize_audio_json(
        self,
        text: str,
        target_lang: str,
        source_is_english: bool = True,
    ) -> dict:
        """
        Generate audio and return both the file URL and the Base64 Data URI
        for instant in-browser HTML5 playback without a second request.
        """
        filename = f"response_{uuid.uuid4().hex}_{target_lang}.mp3"
        output_path = str(_AUDIO_DIR / filename)

        result = await self.engine.generate_regional_response(
            raw_response=text,
            target_lang=target_lang,
            output_file=output_path,
            source_is_english=source_is_english,
        )

        audio_b64 = ""
        if os.path.exists(output_path):
            with open(output_path, "rb") as fh:
                audio_b64 = base64.b64encode(fh.read()).decode("utf-8")

        _delete_after(output_path, _AUDIO_TTL_SECONDS)

        return {
            **result,
            "audio_base64": f"data:audio/mp3;base64,{audio_b64}",
            "audio_url":    f"/voice/audio/{filename}",
            "output_path":  output_path,
        }

    # ------------------------------------------------------------------
    # 6. Metadata helpers
    # ------------------------------------------------------------------

    def get_supported_languages(self) -> list[dict]:
        """Return the list of supported regional languages and their voices."""
        return self.SUPPORTED_LANGUAGES

    @property
    def audio_dir(self) -> Path:
        """Expose audio_tmp path so router.py can serve files from it."""
        return _AUDIO_DIR


# Module-level singleton — lazy engine init on first call
language_service = LanguageService()
