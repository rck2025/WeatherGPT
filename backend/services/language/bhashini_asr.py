"""
Bhashini ASR (Speech Recognition) Fallback Integration.

Government of India Digital India Bhashini ULCA Speech Recognition Gateway.
Trained specifically on diverse regional and rural Indian accents (Bengali, Tamil,
Marathi, Telugu, Malayalam, etc.) to outperform standard Whisper models on regional dialects.
"""

import base64
import logging
import os
import requests

logger = logging.getLogger(__name__)

BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY")
BHASHINI_USER_ID = os.getenv("BHASHINI_USER_ID", "sih-weather-gpt")
BHASHINI_INFERENCE_URL = os.getenv(
    "BHASHINI_INFERENCE_URL",
    "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
)

# Top problematic accent languages designated for Bhashini ASR fallback
BHASHINI_ASR_SUPPORTED_LANGUAGES = {"bn", "ta", "mr", "te", "ml", "or"}

# Language mapping for Bhashini ULCA
BHASHINI_ASR_LANG_MAP = {
    "bn": "bn",
    "ta": "ta",
    "mr": "mr",
    "te": "te",
    "ml": "ml",
    "hi": "hi",
    "gu": "gu",
    "kn": "kn",
    "pa": "pa",
    "or": "or",
    "ur": "ur",
    "as": "as",
}


def is_bhashini_asr_active() -> bool:
    """Check if Bhashini API credentials are configured."""
    key = os.getenv("BHASHINI_API_KEY") or BHASHINI_API_KEY
    return bool(key and key.strip() and not key.strip().startswith("your_"))


def bhashini_transcribe(audio_path: str, target_lang: str) -> dict | None:
    """
    Transcribe audio via Bhashini ULCA ASR pipeline.

    Parameters:
        audio_path: Path to the 16 kHz WAV audio file.
        target_lang: ISO 639-1 language code (e.g. 'bn', 'ta', 'mr', 'te', 'ml').

    Returns:
        Dict with keys:
            - text: Transcribed text string
            - detected_lang: Language code
            - confidence: Confidence float (e.g. 0.92)
            - transcription_method: "Bhashini"
        Or None if Bhashini is not configured or fails.
    """
    norm_lang = (target_lang or "").strip().lower().split("-")[0]
    if norm_lang not in BHASHINI_ASR_SUPPORTED_LANGUAGES and norm_lang not in BHASHINI_ASR_LANG_MAP:
        logger.debug("Language '%s' not in Bhashini ASR target set; skipping.", norm_lang)
        return None

    if not is_bhashini_asr_active():
        logger.debug("Bhashini API key not configured; skipping Bhashini ASR fallback.")
        return None

    if not os.path.exists(audio_path):
        logger.warning("Audio path does not exist for Bhashini ASR: %s", audio_path)
        return None

    try:
        with open(audio_path, "rb") as af:
            audio_b64 = base64.b64encode(af.read()).decode("utf-8")

        key = os.getenv("BHASHINI_API_KEY") or BHASHINI_API_KEY
        bhashini_lang = BHASHINI_ASR_LANG_MAP.get(norm_lang, norm_lang)

        headers = {
            "Accept": "*/*",
            "User-Agent": "WeatherGPT-BhashiniASR-SIH2026/1.0",
            "Authorization": key,
            "Content-Type": "application/json",
        }

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {
                            "sourceLanguage": bhashini_lang,
                        },
                        "audioFormat": "wav",
                        "samplingRate": 16000,
                    },
                }
            ],
            "inputData": {
                "audio": [
                    {
                        "audioContent": audio_b64,
                    }
                ]
            },
        }

        resp = requests.post(BHASHINI_INFERENCE_URL, headers=headers, json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        pipeline_res = data.get("pipelineResponse", [])
        if pipeline_res and "output" in pipeline_res[0]:
            outputs = pipeline_res[0]["output"]
            if outputs and isinstance(outputs, list):
                # Standard Bhashini ASR returns output text in 'source'
                out_item = outputs[0]
                text = out_item.get("source") or out_item.get("target") or ""
                if text.strip():
                    logger.info("💎 [BHASHINI ASR SUCCESS] Language: %s | Text: '%s'", norm_lang, text)
                    return {
                        "text": text.strip(),
                        "detected_lang": norm_lang,
                        "confidence": 0.95,
                        "transcription_method": "Bhashini",
                    }

        logger.warning("Bhashini ASR returned unexpected payload: %s", data)
        return None

    except Exception as exc:
        logger.warning("Bhashini ASR request failed (%s); falling back to Whisper.", exc)
        return None
