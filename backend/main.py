from fastapi import FastAPI, HTTPException

from backend.schemas import ChatRequest, ChatResponse
from backend.services.location.resolver import location_resolver
from backend.services.rag.adapter import rag_service
from backend.services.weather.open_meteo import open_meteo_service

app = FastAPI(
    title="WeatherGPT API",
    version="0.1.0",
)


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
