"""
Bhashini Tier-1 National Translation Bridge
Government of India (MoES / MeitY) ULCA NMT Pipeline with automatic Deep-Translator Fallback.
"""
import logging
import os
import re
import sys
import requests
from dotenv import load_dotenv

from backend.services.language.cleaner import safe_translate

# Ensure environment is refreshed
load_dotenv()

logger = logging.getLogger(__name__)


def _terminal_log(msg: str) -> None:
    """Safely print UTF-8 text with emojis across all terminal encodings."""
    try:
        if hasattr(sys.stdout, "buffer") and sys.stdout.buffer:
            sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
        else:
            print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

BHASHINI_API_KEY = os.getenv("BHASHINI_API_KEY")
BHASHINI_USER_ID = os.getenv("BHASHINI_USER_ID", "135c3e6980-4b41-4cc5-91ce-dc3a356cf841")
BHASHINI_INFERENCE_URL = os.getenv(
    "BHASHINI_INFERENCE_URL",
    "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
)

# Standard Bhashini ISO-639 codes map
BHASHINI_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "bn": "bn",
    "ta": "ta",
    "te": "te",
    "mr": "mr",
    "gu": "gu",
    "kn": "kn",
    "ml": "ml",
    "ur": "ur",
    "pa": "pa",
    "or": "or",
    "as": "as",
    "sa": "sa",
    "ne": "ne",
}


def is_bhashini_active() -> bool:
    """Check if Bhashini API key is configured."""
    key = os.getenv("BHASHINI_API_KEY") or BHASHINI_API_KEY
    return bool(key and key.strip() and not key.strip().startswith("your_"))


def bhashini_translate(text: str, source_lang: str = "en", target_lang: str = "hi") -> str:
    """
    Direct translation via Bhashini National ULCA NMT pipeline.
    Uses official Government of India (MeitY) Dhruva inference endpoint.
    """
    key = os.getenv("BHASHINI_API_KEY") or BHASHINI_API_KEY
    user_id = os.getenv("BHASHINI_USER_ID") or BHASHINI_USER_ID or "135c3e6980-4b41-4cc5-91ce-dc3a356cf841"
    src = BHASHINI_LANG_MAP.get(source_lang, source_lang)
    tgt = BHASHINI_LANG_MAP.get(target_lang, target_lang)

    headers = {
        "Accept": "*/*",
        "User-Agent": "WeatherGPT-BhashiniBridge-SIH2026/1.0",
        "Authorization": key,
        "ulcaApiKey": key,
        "userID": user_id,
        "userId": user_id,
        "Content-Type": "application/json",
    }

    payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": src,
                        "targetLanguage": tgt,
                    }
                }
            }
        ],
        "inputData": {
            "input": [
                {
                    "source": text
                }
            ]
        }
    }

    resp = requests.post(BHASHINI_INFERENCE_URL, headers=headers, json=payload, timeout=8)
    resp.raise_for_status()
    data = resp.json()

    # Extract target text from standard Bhashini response structure
    pipeline_res = data.get("pipelineResponse", [])
    if pipeline_res and "output" in pipeline_res[0]:
        outputs = pipeline_res[0]["output"]
        if outputs and "target" in outputs[0]:
            return outputs[0]["target"]

    raise ValueError("Invalid response structure received from Bhashini pipeline.")


def translate_text(text: str, source_lang: str = "en", target_lang: str = "en") -> str:
    """
    Unified Tier-1 translation entry point:
    1. If source and target are identical or text is empty, returns immediately.
    2. If BHASHINI_API_KEY is detected:
       - Logs: 💎 [BHASHINI CORE ACTIVE]: National-Standard NMT engaged for {language_code}
       - Dispatches request to Bhashini National Language Gateway.
    3. If Bhashini fails or key is missing:
       - Seamlessly falls back to deep_translator (Google/MyMemory).
    """
    if not text or not text.strip():
        return text

    src = source_lang.split("-")[0].lower() if source_lang else "en"
    tgt = target_lang.split("-")[0].lower() if target_lang else "en"

    # Task 3: Linguistic Lock against language drift (e.g. bn -> mr)
    if tgt == "mr" and src == "bn":
        import warnings
        warnings.warn("Potential Language Drift Detected. Reverting to BN.", category=UserWarning)
        logger.warning("🚨 [LINGUISTIC DRIFT PREVENTED] translate_text: target='mr' with src='bn'. Reverting to 'bn'.")
        tgt = "bn"

    if src == tgt:
        return text

    if is_bhashini_active():
        _terminal_log(f"\n💎 [BHASHINI CORE ACTIVE]: National-Standard NMT engaged for {tgt}.")
        logger.info("💎 [BHASHINI CORE ACTIVE]: National-Standard NMT engaged for %s (%s -> %s)", tgt, src, tgt)
        try:
            translated = bhashini_translate(text, source_lang=src, target_lang=tgt)
            if translated and translated.strip():
                return translated
        except Exception as exc:
            _terminal_log(f"⚠️ [BHASHINI FALLBACK] Pipeline failed ({exc}); routing to deep_translator...")
            logger.warning("Bhashini translation failed (%s); seamlessly falling back to deep_translator.", exc)
    else:
        logger.debug("BHASHINI_API_KEY not set; using standard deep_translator pipeline.")

    # Seamless fallback to deep_translator
    return safe_translate(text, source_lang=src, target_lang=tgt)
