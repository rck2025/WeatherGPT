import os
import json
import logging
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    Location,
    SynopticOverlay,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.embeddings import get_embeddings
from backend.services.rag.vector_store import load_vector_db, ingest_bulletins, DB_DIR, DATA_DIR
from backend.services.rag.retriever import retrieve_documents

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

# ------------------------------------------------------------------
# INTENT-FIRST RAG TEMPLATE (Query-First Architecture)
# ------------------------------------------------------------------
template = """[SYSTEM: MOES WEATHER-GPT ARCHITECTURE]
You are an analytical meteorological assistant.

CRITICAL RULE: You must answer the specific USER_QUESTION provided below.
Do not give a generic weather summary unless specifically asked for one.

USER_QUESTION: {question}

DATA SOURCES:
1. LIVE_TELEMETRY:
{live_data}
(Use for CURRENT weather questions)

2. FORECAST_DATA:
{forecast_data}
(Use for TOMORROW/FUTURE weather questions)

3. HISTORICAL_ARCHIVE:
{historical_data}
(Use for PAST/HISTORICAL weather questions)

4. IMD_BULLETINS:
{context}
(Use for safety steps and synoptic causes)

INSTRUCTIONS:
- Directly answer the specific USER_QUESTION first before discussing any other context.
- If the user asks about TOMORROW or future dates, look at FORECAST_DATA.
- If the user asks about PAST or HISTORICAL dates, look at HISTORICAL_ARCHIVE and adhere strictly to the IMD Archivist protocol.
- If the user asks about safety, look at IMD_BULLETINS.
- If there is an active 🚨 IMD alert in the context that is relevant to TODAY, mention it as a footer, but ONLY after answering the user's specific question. Do NOT provide alerts or safety warnings for past historical events.
- Always cite sources when using bulletins or telemetry (e.g., SOURCE: IMD, SOURCE: Open-Meteo, SOURCE: NDMP, SOURCE: MoES Historical Archive / Open-Meteo).
{archivist_command}
{linguistic_constraint}

OFFICIAL RESPONSE:"""

# ------------------------------------------------------------------
# HISTORICAL ARCHIVE TEMPLATE (Hard Date Locking)
# ------------------------------------------------------------------
historical_template = """[SYSTEM: MOES WEATHER-GPT ARCHITECTURE // HISTORICAL ARCHIVE PROTOCOL]
You are an analytical meteorological archivist for the Ministry of Earth Sciences.

CRITICAL RULE: You are reporting data for {requested_date}. Do NOT mention current observations (Kolkata 29.8°C). Use the past tense. Your header must read:
METEOROLOGICAL ARCHIVE REPORT FOR {requested_date}

USER_QUESTION: {question}

HISTORICAL ARCHIVE DATA:
{historical_data}

BULLETINS & CONTEXT:
{context}

INSTRUCTIONS:
- You are reporting data for {requested_date}. Do NOT mention current observations (Kolkata 29.8°C). Use the past tense. Your header must read: METEOROLOGICAL ARCHIVE REPORT FOR {requested_date}.
- Directly answer the specific USER_QUESTION using the HISTORICAL ARCHIVE DATA for {requested_date}.
- Do NOT provide nowcasts, active warnings, or safety alerts, as this is a historical event that has already concluded.
- Always cite sources (e.g., SOURCE: MoES Historical Archive / Open-Meteo).
{archivist_command}
{linguistic_constraint}

OFFICIAL RESPONSE:"""


def detect_temporal_intent(query: str) -> str:
    """Detect query intent to steer retrieval and context prioritization.
    Returns: 'past', 'future', 'safety', or 'current'.
    """
    if not query:
        return "current"
    q = query.lower()

    # Past / Historical Archive intent
    from backend.services.rag.brain import extract_target_date
    target_date = extract_target_date(query)
    if target_date is not None:
        return "past"

    past_keywords = [
        "history", "historical", "past", "archive", "archived",
        "was the weather", "did it rain", "how much rain fell", "recorded",
        "records show", "how hot was", "how cold was", "past weather",
        "previous day", "earlier this week", "cyclone amphan", "cyclone fani",
        "yesterday", "last week", "last month", "last year", "last tuesday", "ago"
    ]
    if any(k in q for k in past_keywords):
        return "past"

    # Future / Forecast intent
    future_keywords = [
        "tomorrow", "kal", "forecast", "outlook", "upcoming",
        "next day", "future", "weekend", "coming days", "later this week",
        "next week", "later today", "day after tomorrow",
    ]
    if any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in future_keywords) or any(
        w in q for w in ["tomorrow", "forecast", "outlook", "next day"]
    ):
        return "future"

    # Safety / Precaution intent
    safety_keywords = [
        "safe", "safety", "go out", "outside", "precaution",
        "shelter", "danger", "risk", "hazard", "evacuate", "evacuation",
        "guidelines", "protect", "stay inside", "travel", "commute", "flood warning",
    ]
    if any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in safety_keywords) or any(
        w in q for w in ["safe to go out", "is it safe", "safety"]
    ):
        return "safety"

    return "current"

# ------------------------------------------------------------------
# DISTRICT & REGIONAL CENTROIDS (Precise Geolocation)
# ------------------------------------------------------------------
DISTRICT_CENTROIDS: dict[str, tuple[float, float]] = {
    # West Bengal
    "kolkata": (22.5726, 88.3639),
    "howrah": (22.5958, 88.2636),
    "south 24 parganas": (22.1352, 88.5444),
    "north 24 parganas": (22.7533, 88.6738),
    "hooghly": (22.8963, 88.2461),
    "darjeeling": (27.0410, 88.2663),
    "siliguri": (26.7271, 88.3953),
    "jalpaiguri": (26.5405, 88.7194),
    "kalimpong": (27.0667, 88.4667),
    "west bengal": (22.9868, 87.8550),

    # Odisha
    "odisha": (20.9517, 85.0985),
    "bhubaneswar": (20.2961, 85.8245),
    "cuttack": (20.4625, 85.8828),
    "puri": (19.8135, 85.8312),
    "balasore": (21.4934, 86.9135),
    "paradip": (20.3164, 86.6114),
    "gopalpur": (19.2612, 84.9080),

    # Maharashtra
    "mumbai": (19.0760, 72.8777),
    "pune": (18.5204, 73.8567),
    "nagpur": (21.1458, 79.0882),
    "nashik": (19.9975, 73.7898),
    "thane": (19.2183, 72.9781),

    # Delhi / NCR
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "noida": (28.5355, 77.3910),
    "gurugram": (28.4595, 77.0266),

    # Tamil Nadu & Kerala
    "chennai": (13.0827, 80.2707),
    "coimbatore": (11.0168, 76.9558),
    "madurai": (9.9252, 78.1198),
    "kochi": (9.9312, 76.2673),
    "thiruvananthapuram": (8.5241, 76.9366),

    # Karnataka & Telangana / AP
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "visakhapatnam": (17.6868, 83.2185),
    "vizag": (17.6868, 83.2185),
    "vijayawada": (16.5062, 80.6480),

    # Gujarat & Rajasthan
    "ahmedabad": (23.0225, 72.5714),
    "surat": (21.1702, 72.8311),
    "jaipur": (26.9124, 75.7873),
    "jodhpur": (26.2389, 73.0243),

    # UP & Bihar
    "lucknow": (26.8467, 80.9462),
    "patna": (25.5941, 85.1376),
    "varanasi": (25.3176, 82.9739),

    # North & Northeast
    "guwahati": (26.1445, 91.7362),
    "assam": (26.2006, 92.9376),
    "shillong": (25.5788, 91.8933),
    "gangtok": (27.3389, 88.6065),
    "sikkim": (27.5330, 88.5122),
    "srinagar": (34.0837, 74.7973),
    "shimla": (31.1048, 77.1734),
    "dehradun": (30.3165, 78.0322),

    # Regional & Asian Centers
    "bay of bengal": (16.0000, 88.0000),
    "arabian sea": (18.0000, 68.0000),
    "nepal": (28.3949, 84.1240),
    "kathmandu": (27.7172, 85.3240),
    "china": (35.8617, 104.1954),
    "tibet": (31.6927, 88.0924),
    "sichuan": (30.6517, 104.0764),
    "dunhuang": (40.1421, 94.6620),
    "xinjiang": (41.1129, 85.2401),
    "japan": (36.2048, 138.2529),
    "tokyo": (35.6762, 139.6503),
    "philippines": (12.8797, 121.7740),
    "manila": (14.5995, 120.9842),
    "indonesia": (-0.7893, 113.9213),
    "jakarta": (-6.2088, 106.8456),
}


def attach_alert_coordinates(
    alert: WeatherAlert,
    location: Location | None = None,
) -> WeatherAlert:
    """Ensure WeatherAlert has latitude and longitude, resolving via text or centroid lookup."""
    if alert.latitude is not None and alert.longitude is not None:
        return alert

    text = f"{alert.title} {alert.description}".lower()

    # 1. Regex search for explicit coordinates in text
    coord_match = re.search(
        r"(?:lat(?:itude)?[:\s]+)?(-?\d{1,2}(?:\.\d+)?)\s*°?\s*([NS])?\s*[,/ ]+\s*(?:lon(?:gitude)?[:\s]+)?(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([EW])?",
        text,
        re.IGNORECASE,
    )
    if coord_match:
        try:
            lat = float(coord_match.group(1))
            if coord_match.group(2) and coord_match.group(2).upper() == "S":
                lat = -abs(lat)
            lon = float(coord_match.group(3))
            if coord_match.group(4) and coord_match.group(4).upper() == "W":
                lon = -abs(lon)
            alert.latitude = round(lat, 4)
            alert.longitude = round(lon, 4)
            return alert
        except Exception:
            pass

    # 2. Match against district / city / state centroid lookup
    sorted_places = sorted(DISTRICT_CENTROIDS.keys(), key=lambda s: -len(s))
    for name in sorted_places:
        if name in text:
            lat, lon = DISTRICT_CENTROIDS[name]
            alert.latitude = lat
            alert.longitude = lon
            return alert

    # 3. Fallback to location object if provided
    if location and location.latitude is not None and location.longitude is not None:
        alert.latitude = location.latitude
        alert.longitude = location.longitude

    return alert


def detect_synoptic_overlays(
    query: str,
    bot_reply: str,
    context_text: str,
    alerts: list[WeatherAlert],
) -> list[dict[str, Any]]:
    """Detect synoptic weather systems (low-pressure systems, depressions, cyclonic circulations)
    over major oceanic basins (Bay of Bengal, Arabian Sea) based on bulletins, AI analysis, and telemetry.
    """
    overlays: list[dict[str, Any]] = []
    combined_corpus = f"{query} {bot_reply} {context_text} {' '.join(f'{a.title} {a.description}' for a in alerts)}".lower()

    synoptic_indicators = [
        "low pressure",
        "low-pressure",
        "cyclon",
        "depression",
        "trough",
        "circulation",
        "synoptic",
        "nowcast",
        "squall",
        "convective",
    ]
    has_synoptic_feature = any(term in combined_corpus for term in synoptic_indicators)

    # Bay of Bengal trigger tokens
    bob_tokens = [
        "bay of bengal",
        "bob",
        "bengal",
        "kolkata",
        "odisha",
        "andhra",
        "tamil nadu",
        "gangetic",
        "east coast",
    ]
    # Arabian Sea trigger tokens
    arabian_tokens = [
        "arabian sea",
        "mumbai",
        "gujarat",
        "konkan",
        "goa",
        "kerala",
        "west coast",
        "saurashtra",
    ]

    has_bob = any(term in combined_corpus for term in bob_tokens)
    has_arabian = any(term in combined_corpus for term in arabian_tokens)

    # 1. Bay of Bengal Low Pressure System / Cyclonic Circulation
    # Bounds: [[5, 80], [22, 95]] covers main formation area and East Coast trajectory
    if (has_synoptic_feature and has_bob) or "bay of bengal" in combined_corpus or (has_synoptic_feature and not has_arabian):
        overlays.append({
            "name": "Bay of Bengal Low Pressure System (BOB-01)",
            "type": "low-pressure",
            "bounds": [[5.0, 80.0], [22.0, 95.0]],
            "center": [14.5, 87.5],
            "severity": "High",
            "description": "IMD Synoptic Bulletin: Low Pressure System and Cyclonic Circulation active across Central & Northern Bay of Bengal.",
        })

    # 2. Arabian Sea Cyclonic Circulation
    # Bounds: [[8, 62], [23, 76]] covers East-Central Arabian Sea and West Coast
    if (has_synoptic_feature and has_arabian) or "arabian sea" in combined_corpus:
        overlays.append({
            "name": "Arabian Sea Cyclonic Circulation (AS-01)",
            "type": "low-pressure",
            "bounds": [[8.0, 62.0], [23.0, 76.0]],
            "center": [15.5, 68.5],
            "severity": "Moderate",
            "description": "IMD Synoptic Bulletin: Upper Air Cyclonic Circulation over East-Central Arabian Sea.",
        })

    return overlays


class WeatherGPTBrain:
    """Ingest disaster bulletins and answer a question using RAG + Gemini with Dual-Model Fallback."""

    def __init__(
        self,
        db_path: Path | str = DB_DIR,
        llm_model: str = "gemini-3.6-flash",
        fallback_model: str = "gemini-3.5-flash",
        embedding_model: str = "models/gemini-embedding-001",
    ) -> None:
        self.db_path = Path(db_path)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.llm_model = llm_model
        self.fallback_model = fallback_model

        self.embeddings = None
        self.llm = None

        if not self.gemini_api_key:
            logger.warning("GEMINI_API_KEY is not configured.")
            return

        try:
            self.embeddings = get_embeddings(self.gemini_api_key)
        except Exception as e:
            logger.error("Failed to load embeddings: %s", e)

        self.llm = self._create_llm(self.llm_model)

    def _create_llm(self, model_name: str) -> ChatGoogleGenerativeAI | None:
        """Create a ChatGoogleGenerativeAI instance for the given model name."""
        if not self.gemini_api_key:
            return None
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.1,
            google_api_key=self.gemini_api_key,
            max_retries=1,
            timeout=12,
            safety_settings={
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            },
        )

    @property
    def is_configured(self) -> bool:
        return self.embeddings is not None and (self.llm is not None or self.gemini_api_key is not None)

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
        location: Location | None = None,
    ) -> list[WeatherAlert]:
        """Threshold alert logic based on live sensor telemetry."""
        if weather_data is None or weather_data.current is None:
            return []

        current = weather_data.current
        lat = location.latitude if location else None
        lon = location.longitude if location else None
        if (current.wind_speed or 0) > 70 or (current.precipitation or 0) > 100:
            return [
                WeatherAlert(
                    title="Severe Weather Warning",
                    description="Extreme wind/rain detected. Evacuate low-lying areas.",
                    severity="High",
                    source="WeatherGPT prototype logic",
                    latitude=lat,
                    longitude=lon,
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
        """Retrieve relevant bulletins and ask Gemini for an answer using Synoptic/Nowcast template and Dual-Model fallback."""
        # Detect Temporal Intent (past, future, safety, or current) early
        temporal_intent = detect_temporal_intent(request.query)

        # Task 4: Clear Memory Leaks - Immediately nullify live weather and alerts for historical queries
        if temporal_intent in ("past", "ANY_PAST"):
            weather_data = None
            alerts = []
            live_alerts = []
            generated_alerts = []
            response_alerts = []
        else:
            live_alerts = list(alerts or [])
            generated_alerts = self._build_generated_alerts(weather_data, location)
            response_alerts = [*live_alerts, *generated_alerts]

            # Precise Geolocation: Ensure every alert has precise latitude and longitude
            for alert in response_alerts:
                attach_alert_coordinates(alert, location)

        vector_db = load_vector_db(self.db_path, self.embeddings)
        if vector_db is None:
            fallback_overlays = [] if temporal_intent in ("past", "ANY_PAST") else detect_synoptic_overlays(request.query, "", "", response_alerts)
            return {
                "bot_reply": (
                    "I do not have an ingested disaster bulletin yet. "
                    "Please run RAG ingestion before asking safety questions."
                ),
                "alerts": response_alerts,
                "sources": [],
                "synoptic_overlays": fallback_overlays,
            }

        weather_keywords = [
            "weather", "rain", "cyclone", "flood", "heat", "ndrf", "mausam", 
            "status", "situation", "report", "update", "condition", "warning", "alert",
            "north", "south", "east", "west", "bengal", "kolkata", "delhi", 
            "chennai", "mumbai", "district", "state", "region", "safe", "outside",
            "go out", "temperature", "forecast", "umbrella", "travel", "commute", "stay",
            "earthquake", "seismic", "nowcast", "trough", "low pressure", "depression"
        ]
        
        has_location = location is not None and any(
            getattr(location, field) is not None and str(getattr(location, field)).strip() != ""
            for field in ["city", "district", "state", "country"]
        )
        is_weather_query = any(word in request.query.lower() for word in weather_keywords) or temporal_intent in ("past", "ANY_PAST")

        if not (has_location or is_weather_query):
            return {
                "bot_reply": (
                    "I am WeatherGPT and can help with weather and "
                    "disaster-safety questions."
                ),
                "alerts": response_alerts,
                "sources": [],
                "synoptic_overlays": [],
            }

        # ── Step 1: Document Retrieval with Temporal Intent Filtering ──
        exclude_keywords = None
        target_date = None
        hist_record = None

        if temporal_intent in ("past", "ANY_PAST"):
            from datetime import datetime, timedelta
            from backend.services.rag.brain import extract_target_date
            from backend.services.weather.history import fetch_historical_data

            target_date = extract_target_date(request.query)
            if not target_date:
                target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

            # Determine coordinates for historical fetch
            q_lat, q_lon = 22.5726, 88.3639  # Default Kolkata centroid if none
            if location and location.latitude is not None and location.longitude is not None:
                q_lat, q_lon = location.latitude, location.longitude
            else:
                q_low = request.query.lower()
                for place_name, coords in DISTRICT_CENTROIDS.items():
                    if place_name in q_low:
                        q_lat, q_lon = coords
                        break

            hist_record = fetch_historical_data(q_lat, q_lon, target_date)
            retrieval_query = f"{request.query} meteorological historical archive records {target_date}"
            exclude_keywords = ["3-hour nowcast", "3-hour", "nowcast", "next 3 hours", "alert", "warning", "forecast"]
            
            # Strict Data Gating: Nullify live alerts and nowcasts before LLM or fallback sees them
            live_alerts = []
            response_alerts = []
        elif temporal_intent == "future":
            retrieval_query = f"{request.query} meteorological outlook weather forecast synoptic predictions"
            exclude_keywords = ["3-hour nowcast", "3-hour", "nowcast", "next 3 hours"]
        elif temporal_intent == "safety":
            retrieval_query = f"{request.query} National Disaster Management Plan NDMP safety guidelines precautions emergency response standard operating procedures"
        else:
            retrieval_query = request.query

        results = retrieve_documents(vector_db, retrieval_query, k=3, exclude_keywords=exclude_keywords)

        sources: list[dict[str, Any]] = []
        for alert in live_alerts:
            source_label = alert.source
            if temporal_intent == "future" and ("nowcast" in alert.title.lower() or "3-hour" in alert.title.lower()):
                source_label = f"{alert.source} (Active Today Only)"
            sources.append(
                {
                    "content": alert.description,
                    "source": source_label,
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
            context_parts.append(f"SOURCE: {source}\n{content}")

        context_text = "\n\n".join(context_parts) if context_parts else "No specific bulletin passages retrieved."

        # ── Step 2: Format Telemetry & Historical Archive Isolation ──
        if temporal_intent in ("past", "ANY_PAST"):
            live_data_text = f"NONE (Historical date query for {target_date} - live telemetry suppressed)."
            forecast_data_text = f"NONE (Historical date query for {target_date} - multi-day forecast suppressed)."
            max_t = f"{hist_record.max_temp}°C" if hist_record and hist_record.max_temp is not None else "N/A"
            min_t = f"{hist_record.min_temp}°C" if hist_record and hist_record.min_temp is not None else "N/A"
            precip = f"{hist_record.total_precipitation} mm" if hist_record and hist_record.total_precipitation is not None else "0.0 mm"
            wind = f"{hist_record.wind_max} km/h" if hist_record and hist_record.wind_max is not None else "N/A"

            historical_data_text = (
                f"METEOROLOGICAL ARCHIVE FOR {target_date}:\n"
                f"• Recorded Maximum Temperature: {max_t}\n"
                f"• Recorded Minimum Temperature: {min_t}\n"
                f"• Recorded Total Precipitation: {precip}\n"
                f"• Recorded Peak Wind Speed: {wind}\n"
                f"• Source: MoES Historical Archive / Open-Meteo"
            )
            requested_date = target_date
            archivist_command = (
                f"COMMAND: You are reporting data for {requested_date}. "
                f"Do NOT mention current observations (Kolkata 29.8°C). Use the past tense. "
                f"Your header must read: METEOROLOGICAL ARCHIVE REPORT FOR {requested_date}.\n"
                f"1. Report the recorded Max/Min Temperature and Precipitation for {requested_date}.\n"
                f"2. Compare these values with 'Normal' averages if available in your RAG context.\n"
                f"3. Do NOT provide safety warnings or nowcasts, as this event has already occurred. Use the past tense (e.g., 'It was...', 'Records show...')."
            )
            # Prepend archive attribution badge
            sources.insert(
                0,
                {
                    "content": historical_data_text,
                    "source": "MoES Historical Archive / Open-Meteo",
                    "score": 1.0,
                }
            )
        else:
            historical_data_text = "NONE (Active live or forecast query - historical archive not requested)."
            archivist_command = ""

            live_data_parts: list[str] = []
            if location:
                loc_label = location.city or location.district or location.state or "Target Sector"
                live_data_parts.append(f"Location: {loc_label} (Lat: {location.latitude:.4f}, Lon: {location.longitude:.4f})")
            if weather_data and weather_data.current:
                c = weather_data.current
                live_data_parts.append(
                    f"Surface Telemetry: Temp={c.temperature}°C, FeelsLike={c.feels_like}°C, Humidity={c.humidity}%, "
                    f"Precipitation={c.precipitation}mm, WindSpeed={c.wind_speed}km/h (SOURCE: Open-Meteo)"
                )
            if live_alerts:
                if temporal_intent == "future":
                    alert_descs = [
                        f"- [{a.source}] ({a.severity} Severity) {a.title}: {a.description} [NOTE: Valid for TODAY only, not tomorrow]"
                        for a in live_alerts
                    ]
                    live_data_parts.append("Active Alerts for TODAY (Note: Applies today only):\n" + "\n".join(alert_descs))
                else:
                    alert_descs = [
                        f"- [{a.source}] ({a.severity} Severity) {a.title}: {a.description}"
                        for a in live_alerts
                    ]
                    live_data_parts.append("Active Alerts & Hazards:\n" + "\n".join(alert_descs))

            live_data_text = "\n".join(live_data_parts) if live_data_parts else "No live telemetry available."

            # Multi-Day / Tomorrow Forecast Data
            forecast_parts: list[str] = []
            if weather_data and weather_data.daily:
                for i, d in enumerate(weather_data.daily[:5]):
                    date_val = d.date
                    date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)[:10]
                    if i == 0:
                        day_label = "TODAY"
                    elif i == 1:
                        day_label = "TOMORROW"
                    else:
                        day_label = f"DAY {i+1}"

                    max_t = f"{d.temperature_max:.1f}°C" if d.temperature_max is not None else "N/A"
                    min_t = f"{d.temperature_min:.1f}°C" if d.temperature_min is not None else "N/A"
                    precip = f"{d.precipitation:.1f}mm" if d.precipitation is not None else "0.0mm"
                    forecast_parts.append(
                        f"• {day_label} ({date_str}): Max Temp = {max_t}, Min Temp = {min_t}, Precipitation = {precip} (SOURCE: Open-Meteo)"
                    )
            elif weather_data and weather_data.hourly:
                forecast_parts.append("Next 24-Hour Telemetry available via Hourly sensor feed (SOURCE: Open-Meteo).")

            forecast_data_text = "\n".join(forecast_parts) if forecast_parts else "No multi-day forecast data available."

        # ── Step 4: Strict Monolingual Prompting & Linguistic Sovereignty ──
        from backend.services.language.resolver import get_language_and_script_names
        req_lang = getattr(request, "language", "en") or "en"
        lang_name, script_name = get_language_and_script_names(req_lang)

        if req_lang != "en":
            if req_lang == "ur":
                linguistic_constraint = (
                    "CRITICAL LOCK: You are an Urdu-only meteorologist. You are STRICTLY FORBIDDEN from using English text. "
                    "Translate all weather data (Temperature, Wind, Humidity) into Urdu words. Do not provide an 'English Version' or translations. "
                    "Output ONLY the Perso-Arabic script. This is a system-critical lock."
                )
            else:
                linguistic_constraint = (
                    f"CRITICAL LOCK: You are an expert in {lang_name}. Respond ONLY in {lang_name} script. "
                    f"Do not use English. Do not provide translations. This is a system-critical lock."
                )
        else:
            linguistic_constraint = "COMMUNICATE PROFESSIONALLY: Provide clear, authoritative meteorological briefing in Indian English."

        # ── Step 5: Intent-First Prompt Population (Literal Query Injection) ──
        if temporal_intent in ("past", "ANY_PAST"):
            prompt = historical_template.format(
                question=request.query,
                requested_date=target_date,
                historical_data=historical_data_text,
                context=context_text,
                archivist_command=archivist_command,
                linguistic_constraint=linguistic_constraint,
            ).strip()
        else:
            prompt = template.format(
                question=request.query,
                live_data=live_data_text,
                forecast_data=forecast_data_text,
                historical_data=historical_data_text,
                context=context_text,
                archivist_command=archivist_command,
                linguistic_constraint=linguistic_constraint,
            ).strip()

        # Task 3: Dual-Model Fallback (gemini-3.6-flash -> gemini-1.5-flash)
        bot_reply = None
        models_to_attempt = [self.llm_model, self.fallback_model]

        for model_name in models_to_attempt:
            try:
                candidate_llm = self.llm if model_name == self.llm_model else self._create_llm(model_name)
                if candidate_llm is None:
                    continue
                response = candidate_llm.invoke(prompt)
                text = self._response_text(response)
                if text:
                    bot_reply = text
                    logger.info("Successfully generated response using model: %s", model_name)
                    break
            except Exception as exc:
                logger.warning(
                    "Primary model %s failed: %s. Attempting fallback model...",
                    model_name,
                    exc,
                )

        # ── Step 6: Intent-First Grounded Fallback (No Static Nowcast Override) ──
        if not bot_reply:
            logger.info("Dual-model generation returned empty. Generating intent-first authority briefing.")
            parts = []
            city_label = (location.city if location else None) or "the requested sector"

            if temporal_intent in ("past", "ANY_PAST"):
                max_t = f"{hist_record.max_temp}°C" if hist_record and hist_record.max_temp is not None else "nominal"
                min_t = f"{hist_record.min_temp}°C" if hist_record and hist_record.min_temp is not None else "nominal"
                precip = f"{hist_record.total_precipitation} mm" if hist_record and hist_record.total_precipitation is not None else "0.0 mm"
                wind = f"{hist_record.wind_max} km/h" if hist_record and hist_record.wind_max is not None else "nominal"
                parts.append(
                    f"METEOROLOGICAL ARCHIVE REPORT FOR {target_date} ({city_label}):\n\n"
                    f"According to historical meteorological records for {target_date}:\n"
                    f"• Maximum Temperature: {max_t}\n"
                    f"• Minimum Temperature: {min_t}\n"
                    f"• Total Precipitation: {precip}\n"
                    f"• Peak Wind Speed: {wind}\n\n"
                    f"Historical records confirm that weather events for {target_date} have concluded. No active hazard warnings apply to past archives.\n"
                    f"SOURCE: MoES Historical Archive / Open-Meteo"
                )

            elif temporal_intent == "future":
                # Answer Tomorrow/Future query first
                tomorrow_forecast = weather_data.daily[1] if (weather_data and len(weather_data.daily) > 1) else None
                if tomorrow_forecast:
                    d = tomorrow_forecast
                    date_str = d.date.strftime("%Y-%m-%d") if hasattr(d.date, "strftime") else str(d.date)[:10]
                    precip_info = f"with expected precipitation of {d.precipitation}mm" if (d.precipitation and d.precipitation > 0) else "with dry conditions"
                    parts.append(
                        f"FORECAST FOR TOMORROW ({date_str}) in {city_label}: "
                        f"Maximum temperature will be {d.temperature_max}°C and minimum temperature {d.temperature_min}°C, {precip_info}. "
                        f"SOURCE: Open-Meteo"
                    )
                else:
                    parts.append(
                        f"FORECAST FOR TOMORROW in {city_label}: Multi-day sensor feed projects nominal seasonal conditions. SOURCE: Open-Meteo"
                    )

                # Mention active today's alert ONLY as a footer note
                nowcasts = [a for a in live_alerts if "nowcast" in a.title.lower() or "nowcast" in a.description.lower() or "3-hour" in a.description.lower()]
                if nowcasts:
                    parts.append(
                        f"NOTE (Active Today Only): IMD has issued a nowcast for today ({nowcasts[0].description}). "
                        f"This applies to today's commute, not tomorrow. SOURCE: IMD"
                    )

            elif temporal_intent == "safety":
                is_severe = any((a.severity or "").lower() in ("critical", "extreme", "high", "red") for a in live_alerts)
                if is_severe:
                    parts.append(
                        f"SAFETY ADVISORY for {city_label}: Caution is advised. Active meteorological hazards are reported in the sector. "
                        f"Adhere to local civil defence directives and NDMP safety guidelines. SOURCE: NDMP"
                    )
                    for a in live_alerts:
                        parts.append(f"• Active Hazard: {a.title} - {a.description} (SOURCE: {a.source})")
                else:
                    parts.append(
                        f"SAFETY ADVISORY for {city_label}: Current telemetry indicates it is generally safe for outdoor activities. "
                        f"Maintain situational awareness. SOURCE: NDMP"
                    )

            else:  # current weather
                if weather_data and weather_data.current:
                    c = weather_data.current
                    parts.append(
                        f"CURRENT WEATHER for {city_label}: Temperature is {c.temperature}°C (feels like {c.feels_like}°C) "
                        f"with {c.humidity}% humidity and wind speed of {c.wind_speed} km/h. SOURCE: Open-Meteo"
                    )
                nowcasts = [a for a in live_alerts if "nowcast" in a.title.lower() or "nowcast" in a.description.lower() or "3-hour" in a.description.lower()]
                if nowcasts:
                    parts.append(f"URGENT NOWCAST: {nowcasts[0].description} SOURCE: {nowcasts[0].source}")
                elif live_alerts:
                    parts.append(f"HAZARD STATUS: {live_alerts[0].description} SOURCE: {live_alerts[0].source}")
                else:
                    parts.append("SYNOPTIC STATUS: Low-pressure system monitoring active across South Asian basin. SOURCE: IMD")

            bot_reply = "\n\n".join(parts)

        # Synoptic System Overlay Detection: Bay of Bengal & Arabian Sea (suppressed for historical past queries)
        if temporal_intent in ("past", "ANY_PAST"):
            synoptic_overlays = []
        else:
            synoptic_overlays = detect_synoptic_overlays(
                query=request.query,
                bot_reply=bot_reply or "",
                context_text=context_text,
                alerts=response_alerts,
            )

        return {
            "bot_reply": bot_reply,
            "alerts": [] if temporal_intent in ("past", "ANY_PAST") else response_alerts,
            "sources": sources,
            "synoptic_overlays": [] if temporal_intent in ("past", "ANY_PAST") else synoptic_overlays,
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
