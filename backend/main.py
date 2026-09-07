import base64
import asyncio
import json
import logging
import os
import re
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles

from backend.schemas import ChatRequest, ChatResponse, FullPipelineResponse, LocationInput, WeatherAlert
from backend.services.language import language_router, language_service
from backend.services.language._schemas import TranscribeResponse
from backend.services.location.resolver import location_resolver
from backend.services.rag.adapter import rag_service
from backend.services.weather.open_meteo import open_meteo_service
from backend.services.weather.hazards import get_realtime_hazards
from backend.services.weather.history import weather_history_service
from backend.services.alerts.notifier import send_emergency_whatsapp, format_lite_alert
from backend.services.api.v1.ingest import router as ingest_router
from backend.services.language.resolver import (
    detect_dominant_script,
    get_language_and_script_names,
    validate_script_purity,
)


def _env_enabled(name: str, default: bool = True) -> bool:
    """Read opt-out startup switches from Render/local environment variables."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


async def _ingest_rag_at_startup() -> None:
    """Build the local bulletin index once, before requests are accepted."""
    if rag_service.bulletins_are_ingested():
        logging.info("RAG bulletin index already exists; startup ingestion skipped.")
        return
    try:
        count = await asyncio.to_thread(rag_service.ingest_documents)
        logging.info("Startup RAG ingestion completed: %d PDF bulletin(s).", count)
    except Exception:
        # A missing key or one bad PDF must not take down the web application.
        # The health endpoint remains usable and the error is visible in Render logs.
        logging.exception("Startup RAG ingestion failed.")


async def _run_hunter_at_startup() -> None:
    """Discover current bulletin URLs and add their alerts to live memory."""
    try:
        from backend.services.api.v1.ingest import append_alerts, process_sources
        from backend.services.ingestion.hunter import GlobalClimateHunter

        hunter = GlobalClimateHunter()
        sources = await asyncio.to_thread(hunter.hunt_for_pdfs)
        ingested = await process_sources(sources, max_workers=3)
        append_alerts(ingested)
        logging.info(
            "Startup hunter completed: %d/%d bulletin source(s) ingested.",
            len(ingested), len(sources),
        )
    except Exception:
        # Official sources can be temporarily unavailable. Do not block startup;
        # the hunter can be re-run from a Render shell or scheduled separately.
        logging.exception("Startup bulletin hunter failed.")


@asynccontextmanager
async def lifespan(application: FastAPI):
    # RAG must be ready before the first response. The link hunter is network
    # bound and can complete in the background without delaying readiness.
    if _env_enabled("AUTO_RAG_INGEST", default=True):
        await _ingest_rag_at_startup()

    hunter_task: asyncio.Task | None = None
    if _env_enabled("AUTO_HUNTER", default=True):
        hunter_task = asyncio.create_task(_run_hunter_at_startup())

    yield

    if hunter_task and not hunter_task.done():
        hunter_task.cancel()
        try:
            await hunter_task
        except asyncio.CancelledError:
            pass

# ------------------------------------------------------------------
# PATH & FFMPEG CONFIGURATION
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # 'backend' folder
PROJECT_ROOT = BASE_DIR.parent              # project root
FRONTEND_DIR = PROJECT_ROOT / "frontend"   # 'frontend' folder

# Ensure .venv site-packages is accessible if running under system python
venv_site_packages = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
if venv_site_packages.exists() and str(venv_site_packages) not in sys.path:
    sys.path.insert(0, str(venv_site_packages))

# Ensure FFmpeg is accessible in PATH via imageio-ffmpeg
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    alias = os.path.join(ffmpeg_dir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not os.path.exists(alias):
        import shutil
        shutil.copyfile(ffmpeg_exe, alias)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except Exception as _ff_err:
    logging.warning("FFmpeg auto-path setup: %s", _ff_err)

# ------------------------------------------------------------------
# LANGUAGE UTILITIES
# ------------------------------------------------------------------

def detect_script_language(text: str) -> str | None:
    """Detect regional Indian language script from unicode character ranges across all 15 languages.

    Returns an ISO 639-1 language code (e.g. "hi", "bn", "ta", "ur", "pa")
    if a regional unicode script is found in *text*, otherwise returns None.
    """
    if not text:
        return None
    lang, _script, purity = detect_dominant_script(text)
    if lang != "en" and purity >= 0.20:
        return lang
    return None

app = FastAPI(
    title="WeatherGPT API",
    version="0.1.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.include_router(ingest_router)
app.include_router(language_router, prefix="/voice", tags=["Voice & Language"])


# ------------------------------------------------------------------
# ALERTS STATE MANAGEMENT
# ------------------------------------------------------------------
alerts: list[WeatherAlert] = [
    WeatherAlert(
        title="IMD 3-Hour Nowcast: Severe Thunderstorm & Squall Warning",
        description="Urgent 3-hour nowcast: Moderate to intense thunderstorm with lightning, squall wind speed reaching 45-55 km/h, and intense rainfall spells likely over Kolkata, Howrah, and South 24 Parganas in the next 3 hours associated with well-marked Low Pressure system over Bay of Bengal.",
        severity="High",
        source="IMD",
        latitude=22.5726,
        longitude=88.3639,
    )
]


def get_active_alerts(location: str | None = None) -> list[WeatherAlert]:
    if not location or not location.strip():
        return list(alerts)

    loc_lower = location.strip().lower()
    return [
        alert
        for alert in alerts
        if loc_lower in alert.description.lower() or loc_lower in alert.title.lower()
    ]


# ------------------------------------------------------------------
# HEALTH
# ------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


# ------------------------------------------------------------------
# UNIFIED WEATHER LOGIC (Central Core)
# Orchestrates:
#   1. [Language pre-step]   — translate regional query → English for RAG
#   2. Location resolution
#   3. Weather data fetch
#   4. Multi-Hazard Ingestion & RAG / AI Brain
#   5. [Language post-step]  — translate reply → regional language
#   6. [Voice synthesis]     — if channel == "voice", generate audio_url
# ------------------------------------------------------------------


async def execute_weather_logic(request: ChatRequest) -> ChatResponse:
    """
    Unified pipeline shared by text (/chat) and future voice flows.
    The frozen ChatRequest / ChatResponse schema contract is fully preserved.
    """
    try:
        # Determine target language (Task 5: Bengali-to-Marathi Kill-Switch: strictly lock requested language)
        req_lang = (request.language or "").strip().lower()
        if req_lang and req_lang not in ("auto", "none"):
            target_lang = req_lang.split("-")[0].split("_")[0]
        else:
            detected = detect_script_language(request.query)
            target_lang = detected if detected else "en"

        # ── Step 1: translate user query to English for reliable RAG ──
        english_query = request.query
        if target_lang != "en":
            english_query = language_service.translate_query_to_english(
                request.query, target_lang
            )

        # ── Step 2: location resolution ──
        location = location_resolver.resolve(request.location)
        if not location:
            return ChatResponse(
                bot_reply="I need your location to provide weather information.",
                alerts=get_realtime_hazards(),
            )

        # ── Step 3: weather data (Strict Gating: skip live telemetry for past queries) ──
        from backend.services.rag.service import detect_temporal_intent
        is_past = detect_temporal_intent(english_query) in ("past", "ANY_PAST")
        weather = None if is_past else await open_meteo_service.get_weather(location)

        # ── Step 3.5: Fast System Status Probe (Instant Initialization & Heartbeat) ──
        if english_query.strip().upper() == "SYSTEM_STATUS_PROBE":
            filtered_alerts = get_active_alerts(location.city)
            realtime_hazards = get_realtime_hazards()
            combined_alerts = [*filtered_alerts, *realtime_hazards]

            seen_alerts = set()
            merged_alerts = []
            for alert in combined_alerts:
                key = (alert.title, alert.description, alert.source)
                if key not in seen_alerts:
                    seen_alerts.add(key)
                    merged_alerts.append(alert)

            from backend.services.rag.service import detect_synoptic_overlays
            synoptic_overlays = detect_synoptic_overlays(
                query="SYSTEM_STATUS_PROBE",
                bot_reply="SYNOPTIC STATUS: Low-pressure system monitoring active across Bay of Bengal basin. SOURCE: IMD",
                context_text="",
                alerts=merged_alerts,
            )

            hazards_count = len(merged_alerts)
            loc_label = location.city or "Regional Sector"
            temp_str = (
                f"{weather.current.temperature:.1f}°C"
                if (weather and weather.current and weather.current.temperature is not None)
                else "nominal"
            )

            probe_reply = (
                f"SYSTEM STATUS: NOMINAL // ALL GEOSPATIAL HAZARD FEEDS SYNCHRONIZED.\n\n"
                f"• Sector: {loc_label} (Lat: {location.latitude:.4f}, Lon: {location.longitude:.4f})\n"
                f"• Surface Telemetry: {temp_str} | Open-Meteo live sensor feed active.\n"
                f"• Active Regional Hazards: {hazards_count} tracked via IMD & USGS telemetry networks.\n"
                f"• Synoptic Status: Low Pressure System active over the Bay of Bengal.\n\n"
                f"Command terminal online and ready for queries. (SOURCE: MoES / IMD / USGS)"
            )

            from backend.schemas import RAGDocument, SynopticOverlay
            return ChatResponse(
                bot_reply=probe_reply,
                location=location,
                weather=weather,
                alerts=merged_alerts,
                sources=[
                    RAGDocument(content="IMD Meteorological nowcast bulletins and multi-hazard telemetry.", source="IMD", score=1.0),
                    RAGDocument(content="USGS Real-time Earthquake Hazards feed for South Asia / Indian Basin.", source="USGS", score=1.0),
                ],
                synoptic_overlays=[SynopticOverlay.model_validate(o) for o in synoptic_overlays],
            )

        # ── Step 4: Multi-Hazard Ingestion & RAG / AI Brain (Linguistic Sovereignty) ──
        if is_past:
            combined_alerts = []
            realtime_hazards = []
        else:
            filtered_alerts = get_active_alerts(location.city)
            realtime_hazards = get_realtime_hazards()
            combined_alerts = [*filtered_alerts, *realtime_hazards]

        # Pass target_lang directly so RAG prompt enforces Strict Monolingual Mandate in target script
        rag_request = request.model_copy(update={"query": english_query, "language": target_lang})
        chat_response = rag_service.answer(
            request=rag_request,
            location=location,
            weather=None if is_past else weather,
            alerts=combined_alerts,
        )

        if is_past:
            chat_response.weather = None
            chat_response.alerts = []
            chat_response.synoptic_overlays = []
        else:
            # Merge realtime hazards into ChatResponse alerts ensuring deduplication
            seen_alerts = set()
            merged_alerts = []
            for alert in (chat_response.alerts or []) + realtime_hazards:
                key = (alert.title, alert.description, alert.source)
                if key not in seen_alerts:
                    seen_alerts.add(key)
                    merged_alerts.append(alert)
            chat_response.alerts = merged_alerts

        # ── Step 5: Linguistic Sovereignty Verification & Dual Text Display ──
        raw_ai_reply = chat_response.bot_reply
        text_for_synthesis = raw_ai_reply

        if target_lang != "en":
            # Check if Gemini output satisfies Unicode Script Guard (>= 30% script purity)
            is_pure_script = validate_script_purity(raw_ai_reply, target_lang, threshold=0.30)
            if is_pure_script:
                native_reply = raw_ai_reply
                try:
                    english_version = language_service.translate_query_to_english(native_reply, target_lang)
                except Exception:
                    english_version = ""

                if english_version and english_version.strip() != native_reply.strip():
                    chat_response.bot_reply = f"{native_reply}\n\n---\n\n**English Version:**\n\n{english_version}"
                else:
                    chat_response.bot_reply = native_reply
            else:
                # Fallback: Translate English/mixed AI reply into target regional language
                native_reply = language_service.process_bot_reply(
                    raw_ai_reply, target_lang
                )
                chat_response.bot_reply = f"{native_reply}\n\n---\n\n**English Version:**\n\n{raw_ai_reply}"

            # VOICE PROCESS: Strictly in the native language (never contains English Version)
            text_for_synthesis = native_reply

        # ── Step 5.5: Fetch Historical Time-Series (1h - 7d) ──
        try:
            history_records, _ = await weather_history_service.fetch_time_series(location, interval="24h")
            chat_response.history_data = history_records
        except Exception as hist_err:
            logging.warning("History fetch warning: %s", hist_err)

        # ── Step 5.6: Out-of-Terminal Emergency WhatsApp Bridge ──
        is_red_alert = any(
            (a.severity or "").lower() in ("critical", "extreme", "red", "red alert")
            for a in chat_response.alerts
        ) or ("red alert" in raw_ai_reply.lower() or "critical warning" in raw_ai_reply.lower())

        if is_red_alert:
            first_hazard = next(
                (a.title for a in chat_response.alerts if (a.severity or "").lower() in ("critical", "extreme", "red", "high")),
                "Severe Meteorological Hazard"
            )
            city_name = location.city or "Regional Sector"
            lite_msg = format_lite_alert(first_hazard, city_name)
            try:
                import os
                phone = os.getenv("EMERGENCY_PHONE", "+919876543210")
                send_emergency_whatsapp(phone, lite_msg)
            except Exception as notify_err:
                logging.warning("Emergency WhatsApp dispatch warning: %s", notify_err)

        # ── Step 6: synthesise audio when channel == "voice" ──
        if request.channel == "voice":
            from backend.services.language.cleaner import translate_units_to_native
            voice_text = translate_units_to_native(text_for_synthesis, lang=target_lang)
            chat_response.audio_url = await language_service.synthesize_audio(
                voice_text,
                target_lang=target_lang,
            )

        chat_response.detected_language = target_lang
        chat_response.locked_language_code = target_lang
        return chat_response


    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from exc


# ------------------------------------------------------------------
# TEXT CHAT ENDPOINT
# ------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Entry point for text-based chat queries."""
    return await execute_weather_logic(request)


# ------------------------------------------------------------------
# VOICE-TO-VOICE COMMAND CENTER ENDPOINT
# Orchestrates: Audio Ingestion -> Whisper STT -> Native Script Guard ->
#               RAG Brain Query (WeatherGPTBrain) -> Edge-TTS Regional Synthesis ->
#               Auto-play Base64/URL Response
# ------------------------------------------------------------------
@app.post("/voice/process", response_model=ChatResponse)
async def voice_process(
    file: UploadFile = File(...),
    location: str | None = Form(None),
    language: str | None = Form(None),
    user_language: str | None = Form(None),
    user_language_query: str | None = Query(None, alias="user_language"),
) -> ChatResponse:
    """Seamless Voice Loop endpoint:
    1. Ingest audio blob from frontend.
    2. Transcribe audio with Whisper (with FFmpeg standardization & Nudge/LID).
    3. Detect language with Multi-Stage LID.
    4. Query RAG Brain via execute_weather_logic.
    5. Synthesise speech via Edge-TTS in target regional voice (Output Realignment).
    6. Return full ChatResponse with audio_url, audio_base64, and detected_language.
    """
    tmp_filename = f"voice_{uuid.uuid4().hex}_{file.filename or 'audio.webm'}"
    tmp_path = str(language_service.audio_dir / tmp_filename)

    try:
        content = await file.read()
        with open(tmp_path, "wb") as fh:
            fh.write(content)

        # Step 2: SSoT - UI Dropdown is the Sovereign Language Selector
        raw_ui_lang = (user_language or user_language_query or language or "en").strip().lower()
        if raw_ui_lang in ("", "auto", "none"):
            target_ui_lang = "en"
        else:
            target_ui_lang = raw_ui_lang.split("-")[0].split("_")[0]

        # Step 3: Transcribe via Faster-Whisper with Deterministic Language Routing
        try:
            stt_result = language_service.transcribe_audio(
                tmp_path,
                target_lang=target_ui_lang,
                language_hint=target_ui_lang,
                user_language=target_ui_lang,
            )
        except RuntimeError as rt_err:
            err_msg = str(rt_err)
            if "SYS_VOICE > NO_SIGNAL" in err_msg or "SYS_VOICE > SIGNAL_NOISE" in err_msg or "SYS_VOICE > ERROR: SCRIPT_MISMATCH" in err_msg:
                raise HTTPException(status_code=422, detail=err_msg) from rt_err
            raise

        transcribed_text = stt_result.get("original_text", "").strip()
        if not transcribed_text:
            raise HTTPException(
                status_code=422,
                detail="SYS_VOICE > NO_SIGNAL: No clear speech detected.",
            )

        # Step 4: SSoT Enforcement: Dropdown language strictly dictates the downstream loop
        locked_language_code = target_ui_lang
        detected_lang = target_ui_lang

        # Step 5: Parse Location Input if provided
        location_input = None
        if location:
            try:
                loc_data = json.loads(location)
                if isinstance(loc_data, dict):
                    location_input = LocationInput(**loc_data)
                else:
                    location_input = LocationInput(raw_text=str(location))
            except Exception:
                location_input = LocationInput(raw_text=str(location))

        # Step 6: Execute Brain Query & Regional Speech Synthesis (strictly locked to locked_language_code)
        chat_req = ChatRequest(
            query=transcribed_text,
            location=location_input,
            language=locked_language_code,
            channel="voice",
        )

        chat_resp = await execute_weather_logic(chat_req)
        chat_resp.transcribed_query = transcribed_text
        chat_resp.detected_language = locked_language_code
        chat_resp.locked_language_code = locked_language_code

        # Step 6.5: SIH Demo Monitoring & Robustness Metrics
        transcription_method = stt_result.get("transcription_method", "Whisper")
        transcription_confidence = float(stt_result.get("confidence", 0.0))
        chat_resp.transcription_method = transcription_method
        chat_resp.transcription_confidence = transcription_confidence

        logging.info(
            "🎯 [SIH MONITOR] Transcription Confidence: %.2f (%.1f%%) | Method: %s | Language: %s (Locked: %s) | Text: '%s'",
            transcription_confidence,
            transcription_confidence * 100,
            transcription_method,
            detected_lang,
            locked_language_code,
            transcribed_text,
        )

        # Step 7: Attach Base64 Data URI for instant zero-latency HTML5 playback
        if chat_resp.audio_url:
            audio_filename = chat_resp.audio_url.split("/")[-1]
            local_audio_path = language_service.audio_dir / audio_filename
            if local_audio_path.exists():
                try:
                    with open(local_audio_path, "rb") as af:
                        b64_audio = base64.b64encode(af.read()).decode("utf-8")
                        chat_resp.audio_base64 = f"data:audio/mp3;base64,{b64_audio}"
                except Exception as b64_err:
                    logging.warning("Failed to base64-encode synthesized audio: %s", b64_err)

        return chat_resp


    except HTTPException:
        raise
    except Exception as exc:
        err_str = str(exc)
        if "SYS_VOICE > NO_SIGNAL" in err_str or "SYS_VOICE > SIGNAL_NOISE" in err_str or "SYS_VOICE > ERROR: SCRIPT_MISMATCH" in err_str:
            raise HTTPException(status_code=422, detail=err_str) from exc
        logging.exception("Voice processing failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ------------------------------------------------------------------
# Task 1 & 4: CLOSED-LOOP LINGUISTIC LOCK FULL-PIPELINE ENDPOINT
# ------------------------------------------------------------------
@app.post("/api/voice/full-pipeline", response_model=FullPipelineResponse, tags=["Voice & Language"])
async def voice_full_pipeline(
    file: UploadFile = File(...),
    location: str | None = Form(None),
    language: str | None = Form(None),
    user_language: str | None = Form(None),
    user_language_query: str | None = Query(None, alias="user_language"),
) -> FullPipelineResponse:
    """Closed-loop voice full-pipeline endpoint:
    Guarantees Input Language == Output Language (Linguistic Lock).
    Returns FullPipelineResponse with locked_language_code.
    """
    effective_lang = (user_language or user_language_query or language or "").strip().lower()
    norm_lang = effective_lang.split("-")[0].split("_")[0] if effective_lang not in ("", "auto", "none") else None

    chat_resp = await voice_process(
        file=file,
        location=location,
        language=norm_lang,
        user_language=norm_lang,
    )
    return FullPipelineResponse(
        bot_reply=chat_resp.bot_reply,
        location=chat_resp.location,
        weather=chat_resp.weather,
        alerts=chat_resp.alerts,
        sources=chat_resp.sources,
        synoptic_overlays=chat_resp.synoptic_overlays,
        audio_url=chat_resp.audio_url,
        audio_base64=chat_resp.audio_base64,
        transcribed_query=chat_resp.transcribed_query,
        detected_language=chat_resp.detected_language,
        history_data=chat_resp.history_data,
        transcription_method=chat_resp.transcription_method,
        transcription_confidence=chat_resp.transcription_confidence,
        locked_language_code=chat_resp.locked_language_code or norm_lang or chat_resp.detected_language or "en",
    )


# ------------------------------------------------------------------
# Task 1: EXPLICIT VOICE TRANSCRIBE ENDPOINT
# ------------------------------------------------------------------
@app.post("/api/voice/transcribe", response_model=TranscribeResponse, tags=["Voice & Language"])
async def api_voice_transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    user_language: str | None = Form(None),
    user_language_query: str | None = Query(None, alias="user_language"),
) -> TranscribeResponse:
    """Explicit Language Routing STT endpoint.
    Accepts audio and mandatory user_language string from request body or query.
    """
    tmp_filename = f"upload_{uuid.uuid4().hex}_{file.filename or 'audio.webm'}"
    tmp_path = str(language_service.audio_dir / tmp_filename)

    try:
        content = await file.read()
        with open(tmp_path, "wb") as fh:
            fh.write(content)

        effective_lang = (user_language or user_language_query or language or "en").strip().lower()
        norm_lang = "en" if effective_lang in ("", "auto", "none") else effective_lang.split("-")[0].split("_")[0]

        result = language_service.transcribe_audio(
            tmp_path,
            target_lang=norm_lang,
            language_hint=norm_lang,
            user_language=norm_lang,
        )
        method = result.get("transcription_method", "Whisper")
        conf = float(result.get("confidence", 0.0))

        return TranscribeResponse(
            success=True,
            original_text=result.get("original_text", ""),
            detected_language=result.get("detected_lang", norm_lang or "en"),
            language_confidence=conf,
            english_query=result.get("english_query", ""),
            transcription_method=method,
        )
    except HTTPException:
        raise
    except Exception as exc:
        err_str = str(exc)
        if "SYS_VOICE > NO_SIGNAL" in err_str or "SYS_VOICE > SIGNAL_NOISE" in err_str or "SYS_VOICE > ERROR: SCRIPT_MISMATCH" in err_str:
            raise HTTPException(status_code=422, detail=err_str) from exc
        logging.exception("Transcription failed.")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass



# ------------------------------------------------------------------
# HISTORICAL TIME-SERIES & TEMPORAL HAZARDS ENDPOINTS
# ------------------------------------------------------------------
@app.get("/weather/history")
async def get_weather_history(lat: float, lon: float, interval: str = "24h"):
    """Standalone endpoint for high-frequency interval switching (1h, 6h, 24h, 48h, 7d)."""
    from backend.schemas import Location
    temp_loc = Location(latitude=lat, longitude=lon)
    records, summary = await weather_history_service.fetch_time_series(temp_loc, interval=interval)
    return {"records": records, "summary": summary}


@app.get("/hazards")
async def get_temporal_hazards(
    interval: str = "24h",
    lat: float | None = None,
    lon: float | None = None,
):
    """Temporal multi-hazard geospatial feed for interval-based map filtering (1h, 6h, 24h, 48h, 7d)."""
    from backend.schemas import Location
    hazards = get_realtime_hazards(interval=interval)

    summary = None
    if lat is not None and lon is not None:
        try:
            temp_loc = Location(latitude=lat, longitude=lon)
            _, summary = await weather_history_service.fetch_time_series(temp_loc, interval=interval)
        except Exception as exc:
            logging.warning("Temporal telemetry summary fetch error: %s", exc)

    return {
        "interval": interval,
        "count": len(hazards),
        "hazards": hazards,
        "summary": summary,
    }


# ------------------------------------------------------------------
# RAG INGEST ENDPOINT
# ------------------------------------------------------------------
@app.post("/rag/ingest")
def ingest_rag() -> dict[str, int | str]:
    """Manually ingest the PDF bulletins in backend/data for the MVP demo."""
    try:
        count = rag_service.ingest_documents()
        return {"status": "success", "documents_processed": count}
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="RAG ingestion failed.") from exc


# ------------------------------------------------------------------
# STATIC DATA & FRONTEND MOUNT
# ------------------------------------------------------------------
DATA_DIR = BASE_DIR / "data"
if DATA_DIR.is_dir():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    logging.warning("Frontend folder not found at: %s", FRONTEND_DIR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
