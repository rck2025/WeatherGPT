"""
Internal-only Pydantic models for the language/voice service.

These are NEVER imported by backend/schemas.py or any other service.
They exist only to type the /voice/* endpoints in router.py and the
engine's return values in service.py.
"""
from pydantic import BaseModel


# -----------------------------------------------------------------------
# STT — Speech to Text
# -----------------------------------------------------------------------

class TranscribeResponse(BaseModel):
    success: bool
    original_text: str
    detected_language: str
    language_confidence: float
    english_query: str
    transcription_method: str = "Whisper"


# -----------------------------------------------------------------------
# TTS — Text to Speech
# -----------------------------------------------------------------------

class SynthesizeRequest(BaseModel):
    text: str
    target_language: str = "hi"
    detected_lang_code: str | None = None
    source_is_english: bool = True



class SynthesizeResponse(BaseModel):
    success: bool
    cleaned_english: str
    spoken_regional_text: str
    target_language: str
    voice_used: str
    audio_base64: str
    audio_url: str


# -----------------------------------------------------------------------
# Supported Languages
# -----------------------------------------------------------------------

class LanguageOption(BaseModel):
    code: str
    name: str
    voice: str
    gender: str
