import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

from backend.schemas import (
    ChatRequest,
    ChatResponse,
    CurrentWeatherData,
    Location,
    RAGDocument,
    WeatherAlert,
    WeatherResponse,
)

logger = logging.getLogger(__name__)


class RAGBrain:
    """
    RAG + Gemini service for WeatherGPT.

    IMPORTANT:
    - Does not define FastAPI routes.
    - Does not define its own Pydantic schemas.
    - Consumes the schemas from backend.schemas.
    - Receives live weather data from the weather service.
    - Returns data compatible with ChatResponse.
    """

    DEFAULT_DATA_DIR = "./backend/data"
    DEFAULT_DB_DIR = "./backend/vector_db"

    EMBEDDING_MODEL = "models/gemini-embedding-001"
    LLM_MODEL = "gemini-3.6-flash"

    def __init__(
        self,
        data_dir: str = DEFAULT_DATA_DIR,
        db_dir: str = DEFAULT_DB_DIR,
    ):
        self.data_dir = data_dir
        self.db_dir = db_dir

        self.vector_db: Optional[Chroma] = None

        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        if not self.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY is not configured. "
                "RAGBrain will not be usable until it is configured."
            )
            return

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=self.EMBEDDING_MODEL,
            google_api_key=self.gemini_api_key,
        )

        self.llm = ChatGoogleGenerativeAI(
            model=self.LLM_MODEL,
            temperature=0.2,
            google_api_key=self.gemini_api_key,
        )

        self._load_existing_vector_db()

    # ------------------------------------------------------------------
    # VECTOR DATABASE
    # ------------------------------------------------------------------

    def _load_existing_vector_db(self) -> None:
        """
        Load an existing Chroma database if one exists.

        We deliberately do not build the database during startup.
        Ingestion is an explicit operation.
        """

        if not os.path.isdir(self.db_dir):
            logger.info("RAG vector DB does not exist yet: %s", self.db_dir)
            return

        try:
            self.vector_db = Chroma(
                persist_directory=self.db_dir,
                embedding_function=self.embeddings,
            )

            logger.info(
                "Loaded existing RAG vector DB from %s",
                self.db_dir,
            )

        except Exception:
            logger.exception("Failed to load existing RAG vector DB.")
            self.vector_db = None

    def ingest_documents(self) -> int:
        """
        Load PDFs from data_dir, split them, embed them and store them
        in Chroma.

        Returns:
            Number of PDF files processed.
        """

        if not self.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        if not os.path.isdir(self.data_dir):
            raise FileNotFoundError(
                f"RAG data directory does not exist: {self.data_dir}"
            )

        pdf_files = [
            filename
            for filename in os.listdir(self.data_dir)
            if filename.lower().endswith(".pdf")
        ]

        if not pdf_files:
            raise FileNotFoundError(
                f"No PDF files found in {self.data_dir}"
            )

        logger.info(
            "Starting RAG ingestion. PDFs found: %d",
            len(pdf_files),
        )

        loader = PyPDFDirectoryLoader(self.data_dir)
        documents = loader.load()

        if not documents:
            raise RuntimeError(
                "PDF files were found, but no text could be extracted."
            )

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

        chunks = splitter.split_documents(documents)

        logger.info(
            "Loaded %d documents and created %d chunks.",
            len(documents),
            len(chunks),
        )

        self.vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.db_dir,
        )

        logger.info(
            "RAG vector DB created/refreshed at %s",
            self.db_dir,
        )

        return len(pdf_files)

    # ------------------------------------------------------------------
    # RETRIEVAL
    # ------------------------------------------------------------------

    def _retrieve(
        self,
        query: str,
        k: int = 3,
    ) -> tuple[list[RAGDocument], str]:
        """
        Retrieve relevant documents.

        Returns:
            (
                RAGDocument list for ChatResponse.sources,
                combined context for Gemini
            )
        """

        if self.vector_db is None:
            self._load_existing_vector_db()

        if self.vector_db is None:
            return [], ""

        try:
            results = (
                self.vector_db
                .similarity_search_with_relevance_scores(
                    query,
                    k=k,
                )
            )
        except Exception:
            logger.exception("RAG retrieval failed.")
            return [], ""

        rag_documents: list[RAGDocument] = []
        context_parts: list[str] = []

        for document, score in results:
            source_path = document.metadata.get("source", "Unknown source")
            source_name = os.path.basename(source_path)

            page = document.metadata.get("page")

            if page is not None:
                source = f"{source_name} (Page {int(page) + 1})"
            else:
                source = source_name

            content = document.page_content.strip()

            rag_documents.append(
                RAGDocument(
                    content=content[:500],
                    source=source,
                    score=float(score),
                )
            )

            context_parts.append(
                f"SOURCE: {source}\n"
                f"CONTENT:\n{content}"
            )

        return rag_documents, "\n\n".join(context_parts)

    # ------------------------------------------------------------------
    # WEATHER / ALERT LOGIC
    # ------------------------------------------------------------------

    def _build_alerts(
        self,
        weather: Optional[WeatherResponse],
    ) -> list[WeatherAlert]:
        """
        Generate deterministic application-level alerts from live weather.

        These alerts are separate from RAG retrieval.
        """

        if weather is None or weather.current is None:
            return []

        current: CurrentWeatherData = weather.current

        wind = current.wind_speed or 0.0
        precipitation = current.precipitation or 0.0
        temperature = current.temperature or 0.0

        alerts: list[WeatherAlert] = []

        # Preserve the teammate's original threshold logic.
        if wind > 70 or precipitation > 100 or temperature > 45:
            alerts.append(
                WeatherAlert(
                    title="Severe Weather Warning",
                    description=(
                        "Extreme weather conditions detected. "
                        "Follow official disaster-management guidance "
                        "and avoid unsafe or exposed areas."
                    ),
                    severity="High",
                    source="WeatherGPT AI Logic",
                )
            )

        elif wind > 40 or precipitation > 50 or temperature > 40:
            alerts.append(
                WeatherAlert(
                    title="Weather Advisory",
                    description=(
                        "Potentially hazardous weather conditions "
                        "detected. Exercise caution and monitor "
                        "official weather and disaster alerts."
                    ),
                    severity="Moderate",
                    source="WeatherGPT AI Logic",
                )
            )

        return alerts

    # ------------------------------------------------------------------
    # TOPIC GUARDRAIL
    # ------------------------------------------------------------------

    @staticmethod
    def _is_weather_or_disaster_query(query: str) -> bool:
        """
        Determine whether the query is relevant to WeatherGPT.
        """

        keywords = [
            "weather",
            "rain",
            "rainfall",
            "storm",
            "cyclone",
            "flood",
            "flooding",
            "heat",
            "heatwave",
            "temperature",
            "wind",
            "lightning",
            "thunder",
            "cloudburst",
            "disaster",
            "emergency",
            "safety",
            "ndrf",
            "imd",
            "mausam",
            "forecast",
            "monsoon",
            "warning",
            "alert",
        ]

        query_lower = query.lower()

        return any(keyword in query_lower for keyword in keywords)

    # ------------------------------------------------------------------
    # PROMPT
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        request: ChatRequest,
        location: Optional[Location],
        weather: Optional[WeatherResponse],
        alerts: list[WeatherAlert],
        context: str,
    ) -> str:
        """
        Build the Gemini prompt from the existing application objects.
        """

        location_text = "Unknown"

        if location:
            location_parts = [
                location.city,
                location.district,
                location.state,
                location.country,
            ]

            location_text = ", ".join(
                part
                for part in location_parts
                if part
            )

            if not location_text:
                location_text = (
                    f"{location.latitude}, {location.longitude}"
                )

        weather_json = (
            weather.model_dump_json()
            if weather is not None
            else "{}"
        )

        alerts_text = "\n".join(
            (
                f"- {alert.title}: "
                f"{alert.description} "
                f"(Severity: {alert.severity})"
            )
            for alert in alerts
        )

        if not alerts_text:
            alerts_text = "No application-generated alerts."

        return f"""
You are WeatherGPT, a weather and disaster-safety assistant.

Your role:
- Answer weather and disaster-safety questions.
- Use live weather data when it is provided.
- Use retrieved official/reference documents when relevant.
- Do not invent weather measurements, warnings, or facts.
- Clearly distinguish live weather information from general safety guidance.
- Give practical, concise and actionable advice.
- If the retrieved context does not contain enough information, say so.
- Do not claim that a retrieved document is an official warning unless it
  explicitly represents one.
- Respond in the requested language.

REQUESTED LANGUAGE:
{request.language}

LOCATION:
{location_text}

USER QUESTION:
{request.query}

LIVE WEATHER:
{weather_json}

APPLICATION ALERTS:
{alerts_text}

RETRIEVED SAFETY / DISASTER CONTEXT:
{context if context else "No relevant documents were retrieved."}

Now answer the user's question.
"""

    # ------------------------------------------------------------------
    # MAIN RAG OPERATION
    # ------------------------------------------------------------------

    def answer(
        self,
        request: ChatRequest,
        weather: Optional[WeatherResponse] = None,
        location: Optional[Location] = None,
    ) -> ChatResponse:
        """
        Main RAG operation.

        Input:
            ChatRequest
            WeatherResponse
            Location

        Output:
            ChatResponse
        """

        # --------------------------------------------------------------
        # 1. Topic guardrail
        # --------------------------------------------------------------

        if not self._is_weather_or_disaster_query(request.query):
            return ChatResponse(
                bot_reply=(
                    "I am WeatherGPT, and I can help with weather, "
                    "forecasts, weather alerts, and disaster-safety "
                    "questions."
                ),
                location=location,
                weather=weather,
                alerts=[],
                sources=[],
            )

        # --------------------------------------------------------------
        # 2. Build deterministic alerts
        # --------------------------------------------------------------

        alerts = self._build_alerts(weather)

        # --------------------------------------------------------------
        # 3. Retrieve relevant documents
        # --------------------------------------------------------------

        sources, context = self._retrieve(
            query=request.query,
            k=3,
        )

        # --------------------------------------------------------------
        # 4. Handle missing RAG DB
        # --------------------------------------------------------------

        if self.vector_db is None:
            logger.warning(
                "RAG vector database is not available."
            )

        # --------------------------------------------------------------
        # 5. Generate Gemini response
        # --------------------------------------------------------------

        if not self.gemini_api_key or not hasattr(self, "llm"):
            return ChatResponse(
                bot_reply=(
                    "The AI service is not configured right now. "
                    "Please configure GEMINI_API_KEY."
                ),
                location=location,
                weather=weather,
                alerts=alerts,
                sources=sources,
            )

        prompt = self._build_prompt(
            request=request,
            location=location,
            weather=weather,
            alerts=alerts,
            context=context,
        )

        try:
            response = self.llm.invoke(prompt)

            # Gemini/LangChain may return content as a list of blocks
            # instead of a plain string. ChatResponse.bot_reply requires str.
            if hasattr(response, "text"):
                bot_reply = response.text
            elif isinstance(response.content, str):
                bot_reply = response.content
            elif isinstance(response.content, list):
                bot_reply = "\n".join(
                    block.get("text", "")
                    for block in response.content
                    if isinstance(block, dict) and block.get("text")
                ).strip()
            else:
                bot_reply = str(response.content)

            if not isinstance(bot_reply, str):
                bot_reply = str(bot_reply)

        except Exception:
            logger.exception("Gemini response generation failed.")

            return ChatResponse(
                bot_reply=(
                    "I was unable to generate a response right now. "
                    "Please try again."
                ),
                location=location,
                weather=weather,
                alerts=alerts,
                sources=sources,
            )

        # --------------------------------------------------------------
        # 6. Return standing ChatResponse contract
        # --------------------------------------------------------------

        return ChatResponse(
            bot_reply=bot_reply,
            location=location,
            weather=weather,
            alerts=alerts,
            sources=sources,
        )


# ----------------------------------------------------------------------
# Shared service instance
# ----------------------------------------------------------------------

rag_brain = RAGBrain()