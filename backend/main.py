from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.schemas import ChatRequest, ChatResponse, WeatherAlert
from backend.services.location.resolver import location_resolver
from backend.services.rag.adapter import rag_service
from backend.services.weather.open_meteo import open_meteo_service
from backend.api.v1.ingest import router as ingest_router

app = FastAPI(
    title="WeatherGPT API",
    version="0.1.0",
)

app.include_router(ingest_router)

alerts: list[WeatherAlert] = []


def get_active_alerts(location: str | None = None) -> list[WeatherAlert]:
    if not location or not location.strip():
        return list(alerts)

    loc_lower = location.strip().lower()
    return [
        alert
        for alert in alerts
        if loc_lower in alert.description.lower() or loc_lower in alert.title.lower()
    ]


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
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
        filtered_alerts = get_active_alerts(location.city)

        return rag_service.answer(
            request=request,
            location=location,
            weather=weather,
            alerts=filtered_alerts,
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
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
