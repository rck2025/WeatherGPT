"""Stable bridge between the FastAPI application and the RAG teammate's code."""

import logging
from typing import Any

from backend.schemas import (
    ChatRequest,
    ChatResponse,
    Location,
    RAGDocument,
    SynopticOverlay,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.service import WeatherGPTBrain

logger = logging.getLogger(__name__)


class RAGService:
    """Expose one shared-contract interface while keeping RAG implementation isolated."""

    def __init__(self, brain: WeatherGPTBrain | None = None) -> None:
        self._brain = brain

    @property
    def brain(self) -> WeatherGPTBrain:
        # Lazy construction keeps application startup fast and makes this class
        # simple to replace with a fake in tests.
        if self._brain is None:
            self._brain = WeatherGPTBrain()
        return self._brain

    @staticmethod
    def _as_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(
                block.get("text", "")
                for block in value
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ).strip()
        return str(value)

    @staticmethod
    def _as_alerts(value: Any) -> list[WeatherAlert]:
        return [WeatherAlert.model_validate(item) for item in (value or [])]

    @staticmethod
    def _as_sources(value: Any) -> list[RAGDocument]:
        return [RAGDocument.model_validate(item) for item in (value or [])]

    @staticmethod
    def _as_overlays(value: Any) -> list[SynopticOverlay]:
        return [SynopticOverlay.model_validate(item) for item in (value or [])]

    def answer(
        self,
        request: ChatRequest,
        location: Location,
        weather: WeatherResponse | None,
        alerts: list[WeatherAlert],
    ) -> ChatResponse:
        """Return a valid frontend response even when RAG is unavailable."""
        if not self.brain.is_configured:
            return ChatResponse(
                bot_reply=(
                    "The AI service is not configured. "
                    "Please set GEMINI_API_KEY and restart the server."
                ),
                location=location,
                weather=weather,
                alerts=alerts,
                synoptic_overlays=[],
            )

        try:
            result = self.brain.answer(
                request=request,
                location=location,
                weather=weather,
                alerts=alerts,
            )
            return ChatResponse(
                bot_reply=self._as_text(result.get("bot_reply", "")),
                location=location,
                weather=weather,
                alerts=self._as_alerts(result.get("alerts", alerts)),
                sources=self._as_sources(result.get("sources", [])),
                synoptic_overlays=self._as_overlays(result.get("synoptic_overlays", [])),
                confidence_score=float(result.get("confidence_score", 1.0)),
                model_disagreement=bool(result.get("model_disagreement", False)),
                icao_code=result.get("icao_code") or getattr(location, "icao_code", None),
                metar_raw=result.get("metar_raw"),
                flight_rules=result.get("flight_rules"),
            )
        except Exception:
            logger.exception("RAG service failed.")
            return ChatResponse(
                bot_reply="I could not generate an AI response right now. Please try again.",
                location=location,
                weather=weather,
                alerts=alerts,
                sources=[],
                synoptic_overlays=[],
                confidence_score=1.0,
                model_disagreement=False,
            )

    @property
    def mock_aws_rain(self) -> float | None:
        return getattr(self.brain, "mock_aws_rain", None)

    @mock_aws_rain.setter
    def mock_aws_rain(self, val: float | None) -> None:
        self.brain.mock_aws_rain = val

    @property
    def mock_station_name(self) -> str | None:
        return getattr(self.brain, "mock_station_name", None)

    @mock_station_name.setter
    def mock_station_name(self, val: str | None) -> None:
        self.brain.mock_station_name = val

    @property
    def mock_lightning_strikes(self) -> int | None:
        return getattr(self.brain, "mock_lightning_strikes", None)

    @mock_lightning_strikes.setter
    def mock_lightning_strikes(self, val: int | None) -> None:
        self.brain.mock_lightning_strikes = val

    def ingest_documents(self) -> int:
        """Ingest the PDFs in backend/data and return the processed file count."""
        return self.brain.ingest_bulletins()


rag_service = RAGService()
