from fastapi import FastAPI, HTTPException

from backend.schemas import ChatRequest, ChatResponse
from backend.services.location.resolver import location_resolver


app = FastAPI(
    title="WeatherGPT API",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        location = location_resolver.resolve(request.location)

        return ChatResponse(
            bot_reply="Location resolved successfully."
            if location
            else "I need your location to provide weather information.",
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