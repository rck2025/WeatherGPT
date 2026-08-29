import logging
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.schemas import ChatRequest, ChatResponse
from backend.services.language import language_router, language_service
from backend.services.location.resolver import location_resolver
from backend.services.rag.adapter import rag_service
from backend.services.weather.open_meteo import open_meteo_service


# ------------------------------------------------------------------
# LANGUAGE UTILITIES
# ------------------------------------------------------------------

def detect_script_language(text: str) -> str | None:
    """Detect regional Indian language script from unicode character ranges.

    Returns an ISO 639-1 language code (e.g. "hi", "bn") if a regional
    unicode script is found in *text*, otherwise returns None.
    Only checks native script codepoints — Romanized/Hinglish text returns None.
    """
    if not text:
        return None
    for char in text:
        code = ord(char)
        if 0x0900 <= code <= 0x097F: return "hi"  # Devanagari (Hindi / Marathi)
        if 0x0980 <= code <= 0x09FF: return "bn"  # Bengali
        if 0x0B80 <= code <= 0x0BFF: return "ta"  # Tamil
        if 0x0C00 <= code <= 0x0C7F: return "te"  # Telugu
        if 0x0C80 <= code <= 0x0CFF: return "kn"  # Kannada
        if 0x0D00 <= code <= 0x0D7F: return "ml"  # Malayalam
        if 0x0A80 <= code <= 0x0AFF: return "gu"  # Gujarati
        if 0x0600 <= code <= 0x06FF: return "ur"  # Urdu / Arabic
    return None

# ------------------------------------------------------------------
# PATH CONFIGURATION (MacOS / Platform Independent)
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # 'backend' folder
PROJECT_ROOT = BASE_DIR.parent              # project root
FRONTEND_DIR = PROJECT_ROOT / "frontend"   # 'frontend' folder

app = FastAPI(
    title="WeatherGPT API",
    version="0.1.0",
)

# ------------------------------------------------------------------
# VOICE & LANGUAGE ROUTER
# Mounted under /voice — exposes /voice/languages, /voice/transcribe,
# /voice/synthesize, /voice/synthesize-json, /voice/audio/{filename}
# ------------------------------------------------------------------
app.include_router(language_router, prefix="/voice", tags=["Voice & Language"])


# ------------------------------------------------------------------
# HEALTH
# ------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


# ------------------------------------------------------------------
# UNIFIED WEATHER LOGIC (Central Core)
# Orchestrates:
#   1. [Language pre-step]   — translate regional query → English for RAG
#   2. Location resolution
#   3. Weather data fetch
#   4. RAG / AI Brain
#   5. [Language post-step]  — translate reply → regional language
#   6. [Voice synthesis]     — if channel == "voice", generate audio_url
# ------------------------------------------------------------------


async def execute_weather_logic(request: ChatRequest) -> ChatResponse:
    """
    Unified pipeline shared by text (/chat) and future voice flows.
    The frozen ChatRequest / ChatResponse schema contract is fully preserved.
    """
    try:
        # Determine target language (from request or auto-detected from query script)
        target_lang = request.language or "en"
        if target_lang == "en":
            detected = detect_script_language(request.query)
            if detected:
                target_lang = detected

        # ── Step 1: translate user query to English for reliable RAG ──
        english_query = request.query
        if target_lang != "en":
            english_query = language_service.translate_query_to_english(
                request.query, target_lang
            )

        # ── Step 2: location resolution ──
        location = location_resolver.resolve(request.location)
        if not location:
            return ChatResponse(
                bot_reply="I need your location to provide weather information."
            )

        # ── Step 3: weather data ──
        weather = await open_meteo_service.get_weather(location)

        # ── Step 4: RAG / AI Brain (always in English) ──
        alerts = []
        # Use model_copy so the original frozen request object is never mutated
        english_request = request.model_copy(update={"query": english_query})
        chat_response = rag_service.answer(
            request=english_request,
            location=location,
            weather=weather,
            alerts=alerts,
        )

        # ── Step 5: translate bot_reply into the user's target language ──
        original_english_reply = chat_response.bot_reply
        text_for_synthesis = original_english_reply

        if target_lang != "en":
            translated_reply = language_service.process_bot_reply(
                original_english_reply, target_lang
            )
            text_for_synthesis = translated_reply
            chat_response.bot_reply = f"{translated_reply}\n\n---\n\n**English Version:**\n\n{original_english_reply}"

        # ── Step 6: synthesise audio when channel == "voice" ──
        if request.channel == "voice":
            chat_response.audio_url = await language_service.synthesize_audio(
                text_for_synthesis,
                target_lang=target_lang,
            )

        return chat_response

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from exc


# ------------------------------------------------------------------
# TEXT CHAT ENDPOINT
# ------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Entry point for text-based chat queries."""
    return await execute_weather_logic(request)


# ------------------------------------------------------------------
# RAG INGEST ENDPOINT
# ------------------------------------------------------------------
@app.post("/rag/ingest")
def ingest_rag() -> dict[str, int | str]:
    """Manually ingest the PDF bulletins in backend/data for the MVP demo."""
    try:
        count = rag_service.ingest_documents()
        return {"status": "success", "documents_processed": count}
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="RAG ingestion failed.") from exc


# ------------------------------------------------------------------
# FRONTEND STATIC MOUNT
# Serves the frontend from outside the backend folder so both desktop
# and mobile browsers share the same origin and can call /chat directly.
# IMPORTANT: must be mounted LAST so API routes take priority.
# ------------------------------------------------------------------
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    logging.warning("Frontend folder not found at: %s", FRONTEND_DIR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
