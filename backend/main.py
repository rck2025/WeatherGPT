from fastapi import FastAPI, HTTPException

from backend.schemas import ChatRequest, ChatResponse
from backend.services.location.resolver import location_resolver
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

        return ChatResponse(
            bot_reply=(
                "Weather data fetched successfully."
                if weather
                else "Unable to fetch weather information."
            ),
            location=location,
            weather=weather,
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