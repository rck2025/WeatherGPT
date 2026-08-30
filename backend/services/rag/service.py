import os
import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    Location,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.embeddings import get_embeddings
from backend.services.rag.vector_store import load_vector_db, ingest_bulletins, DB_DIR, DATA_DIR
from backend.services.rag.retriever import retrieve_documents

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


class WeatherGPTBrain:
    """Ingest disaster bulletins and answer a question using RAG + Gemini."""

    def __init__(
        self,
        db_path: Path | str = DB_DIR,
        llm_model: str = "gemini-flash-latest",
        embedding_model: str = "models/gemini-embedding-001",
    ) -> None:
        self.db_path = Path(db_path)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        self.embeddings = None
        self.llm = None

        if not self.gemini_api_key:
            logger.warning("GEMINI_API_KEY is not configured.")
            return

        try:
            self.embeddings = get_embeddings(self.gemini_api_key, model=embedding_model)
        except Exception as e:
            logger.error("Failed to load embeddings: %s", e)

        self.llm = ChatGoogleGenerativeAI(
            model=llm_model,
            temperature=0.1,
            google_api_key=self.gemini_api_key,
            safety_settings={
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            }
        )

    @property
    def is_configured(self) -> bool:
        return self.embeddings is not None and self.llm is not None

    def ingest_bulletins(self, data_path: Path | str = DATA_DIR) -> int:
        """Build or refresh the local Chroma database from PDFs in data_path."""
        return ingest_bulletins(data_path=data_path, db_path=self.db_path, embeddings=self.embeddings)

    @staticmethod
    def _response_text(response: Any) -> str:
        """Normalise Gemini/LangChain text and block responses to a string."""
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text.strip()

        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ).strip()
        return str(content).strip()

    @staticmethod
    def _weather_json(weather_data: WeatherResponse | None) -> str:
        return weather_data.model_dump_json() if weather_data is not None else "{}"

    @staticmethod
    def _location_json(location: Location | None) -> str:
        return location.model_dump_json() if location is not None else "{}"

    @staticmethod
    def _alerts_json(alerts: list[WeatherAlert]) -> str:
        return json.dumps(
            [alert.model_dump() for alert in alerts],
            ensure_ascii=False,
        )

    def _build_generated_alerts(
        self,
        weather_data: WeatherResponse | None,
    ) -> list[WeatherAlert]:
        """Keep the teammate's prototype threshold alert logic."""
        if weather_data is None or weather_data.current is None:
            return []

        current = weather_data.current
        if (current.wind_speed or 0) > 70 or (current.precipitation or 0) > 100:
            return [
                WeatherAlert(
                    title="Severe Weather Warning",
                    description="Extreme wind/rain detected. Evacuate low-lying areas.",
                    severity="High",
                    source="WeatherGPT prototype logic",
                )
            ]
        return []

    def query_with_schemas(
        self,
        request: ChatRequest,
        weather_data: WeatherResponse | None,
        location: Location | None = None,
        alerts: list[WeatherAlert] | None = None,
    ) -> dict[str, Any]:
        """Retrieve relevant bulletins and ask Gemini for an answer."""
        live_alerts = list(alerts or [])
        generated_alerts = self._build_generated_alerts(weather_data)
        response_alerts = [*live_alerts, *generated_alerts]

        vector_db = load_vector_db(self.db_path, self.embeddings)
        if vector_db is None:
            return {
                "bot_reply": (
                    "I do not have an ingested disaster bulletin yet. "
                    "Please run RAG ingestion before asking safety questions."
                ),
                "alerts": response_alerts,
                "sources": [],
            }

        weather_keywords = [
            "weather", "rain", "cyclone", "flood", "heat", "ndrf", "mausam", 
            "status", "situation", "report", "update", "condition", "warning", "alert",
            "north", "south", "east", "west", "bengal", "kolkata", "delhi", 
            "chennai", "mumbai", "district", "state", "region", "safe", "outside",
            "go out", "temperature", "forecast", "umbrella", "travel", "commute", "stay"
        ]
        
        has_location = location is not None and any(
            getattr(location, field) is not None and str(getattr(location, field)).strip() != ""
            for field in ["city", "district", "state", "country"]
        )
        is_weather_query = any(word in request.query.lower() for word in weather_keywords)

        if not (has_location or is_weather_query):
            return {
                "bot_reply": (
                    "I am WeatherGPT and can help with weather and "
                    "disaster-safety questions."
                ),
                "alerts": response_alerts,
                "sources": [],
            }

        results = retrieve_documents(vector_db, request.query, k=3)

        sources: list[dict[str, Any]] = []
        for alert in live_alerts:
            sources.append(
                {
                    "content": alert.description,
                    "source": alert.source,
                    "score": 1.0,
                }
            )
        context_parts: list[str] = []
        for document, score in results:
            page = document.metadata.get("page")
            page_suffix = f" (Page {int(page) + 1})" if page is not None else ""
            source = f"{Path(document.metadata.get('source', 'Unknown')).name}{page_suffix}"
            content = document.page_content.strip()
            sources.append(
                {
                    "content": content[:300],
                    "source": source,
                    "score": float(score),
                }
            )
            context_parts.append(f"SOURCE: {source}\nCONTENT:\n{content}")

        prompt = f"""
[AUTHORITY MODE: MoES WeatherGPT]
You have retrieved info from multiple sources. Rank your answer as follows:
1. If there is a 'Special Weather Bulletin' or 'Red Alert' in the context, start with that.
2. If the user asks about water/floods, prioritize 'Chennai Hydro' or regional RMC reports.
3. If the user asks about crops, prioritize 'Agromet' data.

ALWAYS state the source clearly (e.g., 'According to RMC Guwahati...', 'Based on the Chennai Hydro advisory...', 'According to RMC Kolkata...').

You are the MoES Assistant / WeatherGPT. Even if there is no Red Alert, if the user asks 'Is it safe?', check the context for 'Thunderstorms,' 'High Humidity,' or 'Heatwaves.' Provide a balanced answer like: 'It is 31.3°C in Kolkata. While no Red Alert is active, the humidity is high. According to the National Disaster Management Plan, stay hydrated if going outdoors.'

You have access to a Massive Official Registry:
1. NATIONAL BULLETINS (IMD): Highest priority for general forecasts.
2. DISASTER SOPs (NDRF/NDMA): Highest priority for safety instructions.
3. REGIONAL REPORTS (RMCs): Use these for city-specific details (Kolkata, Mumbai, etc.).
4. AGROMET ADVISORIES (GKMS): Use these ONLY if the user is a farmer or asks about crops.
5. MARINE DATA (INCOIS): Use these for coastal or sea-related queries.

When answering:
- Look at the Metadata 'source' field in the RETRIEVED BULLETINS to identify which category/agency the data belongs to.
- Cite the specific agency (e.g., 'According to INCOIS...', 'Based on the GKMS advisory...', 'RMC Kolkata reports...') for maximum trust.
- Answer the user's question with concise, practical guidance.
- Do not invent weather readings, live alerts, or official warnings.
- Clearly distinguish live data from general safety guidance.

REQUESTED LANGUAGE: {request.language}
LOCATION: {self._location_json(location)}
LIVE WEATHER: {self._weather_json(weather_data)}
LIVE ALERTS: {self._alerts_json(live_alerts)}
RETRIEVED BULLETINS:
{'\n\n'.join(context_parts) if context_parts else 'No bulletin passages were retrieved.'}

QUESTION: {request.query}
""".strip()

        try:
            response = self.llm.invoke(prompt)
            bot_reply = self._response_text(response)
        except Exception:
            logger.exception("Gemini response generation failed.")
            bot_reply = "I could not generate an AI response right now. Please try again."

        return {
            "bot_reply": bot_reply or "I could not generate a response.",
            "alerts": response_alerts,
            "sources": sources,
        }

    def answer(
        self,
        request: ChatRequest,
        location: Location | None,
        weather: WeatherResponse | None,
        alerts: list[WeatherAlert],
    ) -> dict[str, Any]:
        """Stable entry point used by the project adapter."""
        return self.query_with_schemas(
            request=request,
            weather_data=weather,
            location=location,
            alerts=alerts,
        )

    # Backwards-compatible helpers retained from the teammate's prototype.
    def query_with_live_data_detailed(
        self,
        question: str,
        live_json_string: str,
    ) -> dict[str, Any]:
        try:
            data = json.loads(live_json_string) if live_json_string else {}
        except json.JSONDecodeError:
            data = {}

        weather = WeatherResponse(
            current=CurrentWeatherData(
                wind_speed=float(data.get("wind_speed") or data.get("wind") or 0.0),
                precipitation=float(
                    data.get("rainfall")
                    or data.get("rain")
                    or data.get("precipitation")
                    or 0.0
                ),
                temperature=float(data.get("temperature") or data.get("temp") or 0.0),
            )
        )
        return self.query_with_schemas(
            request=ChatRequest(query=question),
            weather_data=weather,
        )

    def query_with_live_data(self, question: str, live_json_string: str) -> str:
        return self.query_with_live_data_detailed(question, live_json_string)["bot_reply"]
