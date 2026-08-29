import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.schemas import ChatRequest, ChatResponse
from backend.services.location.resolver import location_resolver
from backend.services.rag.adapter import rag_service
from backend.services.weather.open_meteo import open_meteo_service

# ------------------------------------------------------------------
# [NEW] PATH CONFIGURATION (MacOS / Platform Independent)
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # This is the 'backend' folder
PROJECT_ROOT = BASE_DIR.parent              # This is the 'WeatherGPT' root
FRONTEND_DIR = PROJECT_ROOT / "frontend"    # This is the 'frontend' folder
app = FastAPI(
    title="WeatherGPT API",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}

# ------------------------------------------------------------------
# [NEW] UNIFIED WEATHER LOGIC (The Central Core)
# ------------------------------------------------------------------
async def execute_weather_logic(request: ChatRequest) -> ChatResponse:
    """
    Unified pipeline used to ensure text and voice (later)
    always provide the same reasoning.
    """
    try:
        # Resolve the user's location first.
        location = location_resolver.resolve(request.location)

        if not location:
            return ChatResponse(
                bot_reply="I need your location to provide weather information."
            )

        # Pass the resolved Location object to Open-Meteo.
        weather = await open_meteo_service.get_weather(location)

        # get live alerts from alerts service
        alerts = []

        return rag_service.answer(
            request=request,
            location=location,
            weather=weather,
            alerts=alerts,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred.",
        ) from exc

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Entry point for text-based chat queries"""
    return await execute_weather_logic(request)


@app.post("/rag/ingest")
def ingest_rag() -> dict[str, int | str]:
    """Manually ingest the PDF bulletins in backend/data for the MVP demo."""
    try:
        count = rag_service.ingest_documents()
        return {"status": "success", "documents_processed": count}
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="RAG ingestion failed.",
        ) from exc


# Serving the frontend from this API gives desktop and phone browsers the same
# origin, so the UI can call /chat without CORS or a hard-coded server address.
# ------------------------------------------------------------------
# [CHANGED] FRONTEND MOUNTING
# ------------------------------------------------------------------
# Serves the static frontend from the folder outside the backend folder
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    logging.warning(f"Frontend folder not found at: {FRONTEND_DIR}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
