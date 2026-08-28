"""RAG and Gemini logic owned by the RAG teammate.

This module deliberately contains no FastAPI routes.  The project-level API
in ``backend.main`` owns HTTP concerns; ``RAGService`` in ``adapter.py``
adapts this class to the shared WeatherGPT schemas.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    Location,
    WeatherAlert,
    WeatherResponse,
)

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DB_DIR = BACKEND_DIR / "vector_db"

# The key lives in backend/.env, not necessarily in the process working
# directory.  Loading this explicit path makes ``uvicorn backend.main:app``
# work consistently from the repository root.
load_dotenv(BACKEND_DIR / ".env")

EMBEDDING_MODEL = "models/gemini-embedding-001"
LLM_MODEL = "gemini-3.6-flash"


class WeatherGPTBrain:
    """Ingest disaster bulletins and answer a question using RAG + Gemini."""

    def __init__(
        self,
        db_path: Path | str = DB_DIR,
        llm_model: str = LLM_MODEL,
        embedding_model: str = EMBEDDING_MODEL,
    ) -> None:
        self.db_path = Path(db_path)
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        self.embeddings: GoogleGenerativeAIEmbeddings | None = None
        self.llm: ChatGoogleGenerativeAI | None = None
        self.vector_db: Chroma | None = None

        if not self.gemini_api_key:
            logger.warning("GEMINI_API_KEY is not configured.")
            return

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=self.embedding_model,
            google_api_key=self.gemini_api_key,
        )
        self.llm = ChatGoogleGenerativeAI(
            model=self.llm_model,
            temperature=0.2,
            google_api_key=self.gemini_api_key,
        )

    @property
    def is_configured(self) -> bool:
        return self.embeddings is not None and self.llm is not None

    def ingest_bulletins(self, data_path: Path | str = DATA_DIR) -> int:
        """Build or refresh the local Chroma database from PDFs in data_path."""
        if not self.is_configured:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        bulletin_dir = Path(data_path)
        pdf_files = sorted(bulletin_dir.glob("*.pdf")) if bulletin_dir.is_dir() else []

        if not pdf_files:
            raise FileNotFoundError(
                f"No PDF bulletins found in {bulletin_dir}."
            )

        documents = []
        for pdf_file in pdf_files:
            documents.extend(PyPDFLoader(str(pdf_file)).load())

        if not documents:
            raise RuntimeError("PDF bulletins were found, but no text could be extracted.")

        chunks = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
        ).split_documents(documents)

        if not chunks:
            raise RuntimeError("No RAG chunks could be created from the PDF bulletins.")

        self.db_path.mkdir(parents=True, exist_ok=True)
        self.vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=str(self.db_path),
        )
        logger.info(
            "Ingested %d PDF bulletin(s) into %s.",
            len(pdf_files),
            self.db_path,
        )
        return len(pdf_files)

    def _load_vector_db(self) -> bool:
        """Load an already-ingested local database when one is available."""
        if self.vector_db is not None:
            return True

        if not self.is_configured or not self.db_path.is_dir():
            return False

        try:
            self.vector_db = Chroma(
                persist_directory=str(self.db_path),
                embedding_function=self.embeddings,
            )
            return True
        except Exception:
            logger.exception("Could not load the RAG vector database.")
            self.vector_db = None
            return False

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

        if not self._load_vector_db():
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
        ]
        if not any(word in request.query.lower() for word in weather_keywords):
            return {
                "bot_reply": (
                    "I am WeatherGPT and can help with weather and "
                    "disaster-safety questions."
                ),
                "alerts": response_alerts,
                "sources": [],
            }

        try:
            results = self.vector_db.similarity_search_with_relevance_scores(
                request.query,
                k=3,
            )
        except Exception:
            logger.exception("RAG retrieval failed.")
            return {
                "bot_reply": "I could not retrieve disaster-safety guidance right now.",
                "alerts": response_alerts,
                "sources": [],
            }

        sources: list[dict[str, Any]] = []
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
You are WeatherGPT, a weather and disaster-safety assistant.
Answer the user's question with concise, practical guidance.
Do not invent weather readings, live alerts, or official warnings.
Clearly distinguish live data from general safety guidance.

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
