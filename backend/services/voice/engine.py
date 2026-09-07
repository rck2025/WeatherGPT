"""Voice engine interface for WeatherGPT."""
from backend.services.language.engine import *
from backend.services.language.service import language_service

def process_query(
    audio_path: str,
    target_lang: str | None = None,
    language_hint: str | None = None,
    user_language: str | None = None,
) -> dict:
    """Explicit Language-Locked transcription entry point with verified ISO code (SSoT)."""
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

def transcribe_audio(
    audio_path: str,
    language: str | None = None,
    user_language: str | None = None,
    target_lang: str | None = None,
) -> dict:
    """Explicit Language-Locked transcription entry point."""
    effective_lang = target_lang or user_language or language or "en"
    kwargs = {
        "language_hint": effective_lang,
        "user_language": effective_lang,
    }
    if target_lang is not None:
        kwargs["target_lang"] = target_lang
    return process_query(audio_path, **kwargs)

transcribe = transcribe_audio

