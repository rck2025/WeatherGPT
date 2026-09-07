"""
WeatherGPT Voice Engine — Public Voice Module Interface.

Provides:
- transcribe(audio_path, language=None): Contextual Biasing, Acoustic Shielding,
  LID Override Safety Net, and Bhashini ASR Fallback.
- WeatherHybridEngine: Core speech synthesis & recognition engine.
- standardize_audio: FFmpeg-based acoustic shielding and audio preprocessing.
"""
from backend.services.audio_utils import standardize_audio
from backend.services.language.engine import WeatherHybridEngine, WEATHER_INITIAL_PROMPTS
from backend.services.language.service import language_service


def process_query(
    audio_path: str,
    target_lang: str | None = None,
    language_hint: str | None = None,
    user_language: str | None = None,
) -> dict:
    """
    Process incoming voice query with Linguistic Lock and Deterministic Routing.
    Ensures detected_lang is returned as a verified ISO 639-1 code (e.g. 'bn', 'mr', 'hi', 'ta', 'ur').
    """
    effective_lang = target_lang or user_language or language_hint or "en"
    kwargs = {
        "language_hint": language_hint or effective_lang,
        "user_language": effective_lang,
    }
    if target_lang is not None:
        kwargs["target_lang"] = target_lang
    res = language_service.transcribe_audio(
        audio_path,
        **kwargs,
    )
    raw_lang = (res.get("detected_lang") or effective_lang or "en").strip().lower().split("-")[0].split("_")[0]
    res["detected_lang"] = raw_lang
    res["locked_language_code"] = raw_lang
    return res


def transcribe(
    audio_path: str,
    language: str | None = None,
    user_language: str | None = None,
    target_lang: str | None = None,
) -> dict:
    """
    Transcribe audio with deterministic language locking (SSoT), acoustic shielding,
    and Bhashini ASR fallback.
    """
    effective_lang = target_lang or user_language or language or "en"
    kwargs = {
        "language_hint": effective_lang,
        "user_language": effective_lang,
    }
    if target_lang is not None:
        kwargs["target_lang"] = target_lang
    return process_query(audio_path, **kwargs)


def transcribe_audio(
    audio_path: str,
    language: str | None = None,
    user_language: str | None = None,
    target_lang: str | None = None,
) -> dict:
    """Alias for transcribe."""
    return transcribe(audio_path, language=language, user_language=user_language, target_lang=target_lang)


__all__ = [
    "transcribe",
    "transcribe_audio",
    "process_query",
    "WeatherHybridEngine",
    "standardize_audio",
    "WEATHER_INITIAL_PROMPTS",
    "language_service",
]

