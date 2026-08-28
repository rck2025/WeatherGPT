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

    Responsibilities:
    - Retrieve relevant disaster/safety documents.
    - Consume live weather data.
    - Understand the user's actual weather question.
    - Select weather data relevant to the question.
    - Generate a concise, practical answer using Gemini.
    - Return data compatible with ChatResponse.
    """

    DEFAULT_DATA_DIR = "./backend/data"
    DEFAULT_DB_DIR = "./backend/vector_db"

    EMBEDDING_MODEL = "models/gemini-embedding-001"
    LLM_MODEL = "gemini-3.6-flash"

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR, db_dir: str = DEFAULT_DB_DIR):
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
        """Load an existing Chroma database if one exists."""

        if not os.path.isdir(self.db_dir):
            logger.info("RAG vector DB does not exist yet: %s", self.db_dir)
            return

        try:
            self.vector_db = Chroma(
                persist_directory=self.db_dir,
                embedding_function=self.embeddings,
            )
            logger.info("Loaded existing RAG vector DB from %s", self.db_dir)
        except Exception:
            logger.exception("Failed to load existing RAG vector DB.")
            self.vector_db = None

    def ingest_documents(self) -> int:
        """
        Load PDFs from data_dir, split them, embed them and store them in Chroma.

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
            raise FileNotFoundError(f"No PDF files found in {self.data_dir}")

        logger.info("Starting RAG ingestion. PDFs found: %d", len(pdf_files))

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

        logger.info("RAG vector DB created/refreshed at %s", self.db_dir)

        return len(pdf_files)

    # ------------------------------------------------------------------
    # RETRIEVAL
    # ------------------------------------------------------------------

    def _retrieve(self, query: str, k: int = 3) -> tuple[list[RAGDocument], str]:
        """
        Retrieve relevant RAG documents.

        Returns:
            RAGDocument list for ChatResponse.sources,
            combined context for Gemini.
        """

        if self.vector_db is None:
            self._load_existing_vector_db()

        if self.vector_db is None:
            return [], ""

        try:
            results = self.vector_db.similarity_search_with_relevance_scores(
                query, k=k
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

    def _build_alerts(self, weather: Optional[WeatherResponse]) -> list[WeatherAlert]:
        """
        Generate deterministic application-level alerts from live weather.
        """

        if weather is None or weather.current is None:
            return []

        current: CurrentWeatherData = weather.current
        wind = current.wind_speed or 0.0
        precipitation = current.precipitation or 0.0
        temperature = current.temperature or 0.0
        alerts: list[WeatherAlert] = []

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
            "weather", "rain", "rainfall", "storm", "cyclone", "flood", "flooding",
            "heat", "heatwave", "temperature", "wind", "lightning", "thunder", "cloudburst",
            "disaster", "emergency", "safety", "ndrf", "imd", "mausam", "forecast", "monsoon",
            "warning", "alert", "umbrella", "raincoat", "jacket", "outdoor", "outside", "picnic",
            "run", "running", "walk", "walking", "travel", "trip", "cycling", "bike", "driving", "drive",
            "rafting", "trekking", "hiking", "mountaineering", "camping", "boating", "paragliding",
            "surfing", "cycling", "travel", "trip", "sikkim", "meghalaya", "himachal", "uttarakhand", "kerala"
        ]

        query_lower = query.lower()
        return any(keyword in query_lower for keyword in keywords)

    # ------------------------------------------------------------------
    # QUERY-AWARE WEATHER CONTEXT
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query_aware_weather_context(
        query: str,
        weather: Optional[WeatherResponse],
    ) -> str:
        """
        Select the weather information relevant to the user's question.

        This prevents Gemini from receiving a large undifferentiated
        weather object and hoping it figures out which date/fields matter.
        """

        if weather is None:
            return "No live weather data is available."

        query_lower = query.lower()
        current = weather.current
        daily = weather.daily or []
        context_parts: list[str] = []

        # --------------------------------------------------------------
        # Time intent
        # --------------------------------------------------------------

        is_tomorrow = any(
            phrase in query_lower
            for phrase in ["tomorrow", "next day", "next 24 hours"]
        )

        is_today = any(
            phrase in query_lower
            for phrase in [
                "today",
                "tonight",
                "right now",
                "currently",
                "current",
                "now",
                "outside",
            ]
        )

        # --------------------------------------------------------------
        # Current conditions
        # --------------------------------------------------------------

        if current is not None and is_today:
            context_parts.append(
                "CURRENT WEATHER:\n"
                f"temperature: {current.temperature} °C\n"
                f"feels_like: {current.feels_like} °C\n"
                f"humidity: {current.humidity}%\n"
                f"wind_speed: {current.wind_speed} km/h\n"
                f"precipitation: {current.precipitation} mm\n"
                f"weather_code: {current.weather_code}"
            )

        # --------------------------------------------------------------
        # Forecast
        # --------------------------------------------------------------

        if daily:
            if is_tomorrow:
                selected_days = daily[:1]
            elif is_today:
                selected_days = daily[:1]
            else:
                selected_days = daily[:5]

            for day in selected_days:
                context_parts.append(
                    "FORECAST:\n"
                    f"date: {day.date}\n"
                    f"temperature_max: {day.temperature_max} °C\n"
                    f"temperature_min: {day.temperature_min} °C\n"
                    f"precipitation: {day.precipitation} mm\n"
                    f"weather_code: {day.weather_code}"
                )

        # --------------------------------------------------------------
        # Practical decision questions
        # --------------------------------------------------------------

        practical_keywords = [
            "umbrella", "rain", "raincoat", "jacket", "coat",
            "run", "running", "walk", "walking", "outdoor",
            "outside", "picnic", "travel", "trip", "bike",
            "cycling", "drive", "driving",
        ]

        is_practical_question = any(
            keyword in query_lower
            for keyword in practical_keywords
        )

        if is_practical_question:
            context_parts.append(
                "PRACTICAL WEATHER DECISION:\n"
                "Use precipitation, temperature, wind and "
                "weather condition for the requested time period "
                "to make the recommendation.\n"
                "Do not give generic advice when live forecast "
                "data is available."
            )

        # --------------------------------------------------------------
        # Adventure questions
        # --------------------------------------------------------------
        adventure_keywords = ["rafting", "trekking", "hiking", "paragliding", "mountaineering", "boating"]
        is_adventure_query = any(k in query_lower for k in adventure_keywords)

        if is_adventure_query:
            context_parts.append(
                "ADVENTURE SPORTS SAFETY RULES:\n"
                "- RAFTING: High risk if precipitation > 10mm or wind > 30km/h. Dangerous during heavy monsoon.\n"
                "- TREKKING: High risk if visibility is low (weather_code > 70) or temperature < 0°C.\n"
                "- PARAGLIDING: Impossible if wind_speed > 20km/h.\n"
                "Combine these rules with the LIVE DATA below to give a definitive 'Go' or 'No-Go' decision."
            )

        # --------------------------------------------------------------
        # Fallback
        # --------------------------------------------------------------

        if not context_parts:
            return weather.model_dump_json()

        return "\n\n".join(context_parts)

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
        Build a query-aware Gemini prompt using a clear hierarchy of truth.
        """

        # --------------------------------------------------------------
        # 1. Handle location
        # --------------------------------------------------------------

        location_text = "Unknown"

        if location:
            location_parts = [
                location.city,
                location.district,
                location.state,
                location.country,
            ]

            location_text = ", ".join(
                part for part in location_parts if part
            )

            if not location_text:
                location_text = f"{location.latitude}, {location.longitude}"

        # --------------------------------------------------------------
        # 2. Handle missing weather
        # --------------------------------------------------------------

        if weather and weather.current:
            weather_context = self._build_query_aware_weather_context(
                request.query,
                weather,
            )
        else:
            weather_context = (
                "Live weather data is currently unavailable "
                "for this location."
            )

        # --------------------------------------------------------------
        # 3. Handle missing alerts
        # --------------------------------------------------------------

        alerts_content = (
            "\n".join(
                f"- {alert.title}: {alert.description}"
                for alert in alerts
            )
            if alerts
            else "No active weather alerts detected by the application."
        )

        # --------------------------------------------------------------
        # 4. Handle missing RAG context
        # --------------------------------------------------------------

        rag_content = (
            context
            if context.strip()
            else "No relevant safety documents were found for this query."
        )

        # --------------------------------------------------------------
        # 5. Build final Gemini prompt
        # --------------------------------------------------------------

        return f"""
    ==================================================
    HIERARCHY OF TRUTH (Follow in this order):
    ==================================================

    1. OFFICIAL ACTIVE ALERTS (Highest Priority):
    {alerts_content}

    If a RED or ORANGE alert is present above, your response
    MUST lead with this warning.

    2. GOVERNMENT SAFETY SOPs (The RAG Knowledge):
    {rag_content}

    Use this for specific safety procedures, helplines,
    evacuation guidance, restrictions, and activity bans.

    3. LIVE SENSOR DATA (The Numbers):
    {weather_context}

    Use this for current temperature, wind, precipitation,
    weather conditions, and specific numerical questions.

    ==================================================
    INSTRUCTIONS:
    ==================================================

    - You are an expert weather and safety officer.

    - Answer the USER'S EXACT QUESTION directly.

    - Follow the HIERARCHY OF TRUTH above.

    - DO NOT ignore Live Weather Data just because there
      is no Official Alert.

    - If Live Weather shows extreme conditions such as
      very high temperature, heavy precipitation, or
      dangerous wind speeds, advise caution even when
      there is no Official Alert.

    - Do NOT invent alerts, weather values, government
      procedures, or safety information.

    - For adventure activities such as rafting, trekking,
      hiking, paragliding, boating, and mountaineering,
      prioritize activity-specific safety rules, bans,
      and restrictions found in the RAG Context.

    - Combine RAG safety guidance with Live Weather Data
      when making activity recommendations.

    - If the available information is insufficient to make
      a reliable safety decision, clearly say so.

    - For "Should I...?" questions, give a clear
      recommendation such as YES, NO, or AVOID.

    - Explain the recommendation using the relevant
      information above.

    - Keep the response concise, practical, and easy to
      understand.

    - Respond in {request.language}.

    ==================================================

    USER QUESTION:
    {request.query}

    LOCATION:
    {location_text}

    ==================================================

    Answer:
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
        Main WeatherGPT operation.
        """

        # --------------------------------------------------------------
        # 1. Topic guardrail
        # --------------------------------------------------------------

        if not self._is_weather_or_disaster_query(request.query):
            return ChatResponse(
                bot_reply=(
                    "I am WeatherGPT, and I can help with "
                    "weather, forecasts, weather alerts, "
                    "and disaster-safety questions."
                ),
                location=location,
                weather=weather,
                alerts=[],
                sources=[],
            )

        # --------------------------------------------------------------
        # 2. Deterministic weather alerts
        # --------------------------------------------------------------

        alerts = self._build_alerts(weather)

        # --------------------------------------------------------------
        # 3. Query-aware RAG retrieval
        # --------------------------------------------------------------

        sources, context = self._retrieve(
            query=request.query,
            k=3,
        )

        # --------------------------------------------------------------
        # 4. Handle unavailable RAG
        # --------------------------------------------------------------

        if self.vector_db is None:
            logger.warning("RAG vector database is not available.")

        # --------------------------------------------------------------
        # 5. Handle unavailable Gemini
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

        # --------------------------------------------------------------
        # 6. Build prompt
        # --------------------------------------------------------------

        prompt = self._build_prompt(
            request=request,
            location=location,
            weather=weather,
            alerts=alerts,
            context=context,
        )

        # --------------------------------------------------------------
        # 7. Generate Gemini response
        # --------------------------------------------------------------

        try:
            response = self.llm.invoke(prompt)

            # Gemini/LangChain may return a plain string or a list
            # of content blocks.

            if hasattr(response, "text"):
                bot_reply = response.text

            elif isinstance(response.content, str):
                bot_reply = response.content

            elif isinstance(response.content, list):
                text_parts = []

                for block in response.content:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if text:
                            text_parts.append(text)

                    elif isinstance(block, str):
                        text_parts.append(block)

                bot_reply = "\n".join(text_parts).strip()

            else:
                bot_reply = str(response.content)

            if not isinstance(bot_reply, str):
                bot_reply = str(bot_reply)

            if not bot_reply.strip():
                bot_reply = (
                    "I couldn't generate a useful weather "
                    "answer right now. Please try again."
                )

        except Exception:
            logger.exception("Gemini response generation failed.")

            return ChatResponse(
                bot_reply=(
                    "I was unable to generate a response right now. Please try again."
                ),
                location=location,
                weather=weather,
                alerts=alerts,
                sources=sources,
            )

        # --------------------------------------------------------------
        # 8. Return ChatResponse
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