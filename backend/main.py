from fastapi import FastAPI, HTTPException

from backend.schemas import ChatRequest, ChatResponse

from backend.services.location.resolver import location_resolver
from backend.services.weather.open_meteo import open_meteo_service
from backend.services.rag.brain import rag_brain

app = FastAPI(
    title="WeatherGPT API",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "rag_loaded": rag_brain.vector_db is not None
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        # --------------------------------------------------------------
        # 1. Resolve location
        # --------------------------------------------------------------
        location = location_resolver.resolve(request.location)

        if not location:
            return ChatResponse(
                bot_reply=(
                    "I need your location to provide weather information."
                )
            )

        # --------------------------------------------------------------
        # 2. Fetch live weather
        # --------------------------------------------------------------
        weather = await open_meteo_service.get_weather(location)

        # --------------------------------------------------------------
        # 3. Run RAG + Gemini
        # --------------------------------------------------------------
        return rag_brain.answer(
            request=request,
            weather=weather,
            location=location,
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

# should be accessible only to admins and not ordinary users
# add authentication later
@app.post("/rag/ingest")
def ingest_rag():
    try:
        count = rag_brain.ingest_documents()

        return {
            "status": "success",
            "documents_processed": count,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG ingestion failed: {exc}",
        ) from exc