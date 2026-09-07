"""Voice module alias forwarding to backend.services.language."""
from backend.services.language.engine import WeatherHybridEngine, standardize_audio
from backend.services.language.service import language_service
from backend.services.language.cleaner import (
    clean_bot_response,
    get_voice_for_language,
    prepare_for_tts,
    safe_translate,
)
from backend.services.language.resolver import (
    calculate_script_purity,
    contains_cjk_characters,
    SCRIPT_REGISTRY,
    validate_script_alignment,
    validate_script_purity,
)

from backend.services.voice.engine import process_query, transcribe, transcribe_audio

__all__ = [
    "transcribe",
    "transcribe_audio",
    "process_query",
    "WeatherHybridEngine",

    "standardize_audio",
    "language_service",
    "clean_bot_response",
    "prepare_for_tts",
    "get_voice_for_language",
    "safe_translate",
    "validate_script_purity",
    "validate_script_alignment",
    "calculate_script_purity",
    "contains_cjk_characters",
    "SCRIPT_REGISTRY",
]

