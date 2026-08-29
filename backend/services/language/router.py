"""
FastAPI router for /voice/* endpoints.

These endpoints speak the module's own internal _schemas only.
They NEVER reference backend.schemas (the frozen contract).

Mounted in main.py as:
    app.include_router(language_router, prefix="/voice", tags=["Voice & Language"])

Endpoints:
    GET  /voice/languages            — list supported regional languages
    POST /voice/transcribe           — audio upload → STT + language detection
    POST /voice/synthesize           — text → MP3 file stream
    POST /voice/synthesize-json      — text → Base64 Data URI JSON
    GET  /voice/audio/{filename}     — serve temporary audio file
"""
import logging
import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.services.language._schemas import (
    LanguageOption,
    SynthesizeRequest,
    SynthesizeResponse,
    TranscribeResponse,
)
from backend.services.language.service import language_service

logger = logging.getLogger(__name__)
router = APIRouter()


# -----------------------------------------------------------------------
# GET /voice/languages
# -----------------------------------------------------------------------

@router.get("/languages", response_model=list[LanguageOption], tags=["Voice & Language"])
def get_languages():
    """Return the list of supported Indian regional languages and their Edge-TTS neural voices."""
    return language_service.get_supported_languages()


# -----------------------------------------------------------------------
# POST /voice/transcribe
# -----------------------------------------------------------------------

@router.post("/transcribe", response_model=TranscribeResponse, tags=["Voice & Language"])
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str | None = Form(None),
):
    """
    Accept any browser audio format (.webm, .ogg, .wav, .mp3, .m4a),
    standardise it to 16 kHz Mono WAV, transcribe with Faster-Whisper,
    detect language, and return the English query ready for the RAG brain.
    """
    tmp_filename = f"upload_{uuid.uuid4().hex}_{file.filename}"
    tmp_path = str(language_service.audio_dir / tmp_filename)

    try:
        content = await file.read()
        with open(tmp_path, "wb") as fh:
            fh.write(content)

        result = language_service.transcribe_audio(tmp_path, language_hint=language)

        return TranscribeResponse(
            success=True,
            original_text=result["original_text"],
            detected_language=result["detected_lang"],
            language_confidence=float(result["confidence"]),
            english_query=result["english_query"],
        )

    except Exception as exc:
        logger.exception("Transcription failed.")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# -----------------------------------------------------------------------
# POST /voice/synthesize  (returns MP3 stream)
# -----------------------------------------------------------------------

@router.post("/synthesize", tags=["Voice & Language"])
async def synthesize_voice_file(request: SynthesizeRequest):
    """
    Clean and translate *text*, then synthesise regional neural audio.
    Returns an MP3 audio stream (audio/mpeg).
    The temporary file is auto-deleted after 120 seconds.
    """
    filename = f"response_{uuid.uuid4().hex}_{request.target_language}.mp3"
    output_path = str(language_service.audio_dir / filename)

    try:
        result = await language_service.engine.generate_regional_response(
            raw_response=request.text,
            target_lang=request.target_language,
            output_file=output_path,
            source_is_english=request.source_is_english,
        )

        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="Audio generation produced no output file.")

        return FileResponse(
            path=output_path,
            media_type="audio/mpeg",
            filename=f"weather_{request.target_language}.mp3",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Speech synthesis failed.")
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {exc}") from exc


# -----------------------------------------------------------------------
# POST /voice/synthesize-json  (returns Base64 Data URI JSON)
# -----------------------------------------------------------------------

@router.post("/synthesize-json", response_model=SynthesizeResponse, tags=["Voice & Language"])
async def synthesize_voice_json(request: SynthesizeRequest):
    """
    Synthesise regional neural audio and return a Base64 Data URI for
    instant in-browser playback via  new Audio(data.audio_base64).play()
    — no secondary HTTP request needed.
    """
    try:
        result = await language_service.synthesize_audio_json(
            text=request.text,
            target_lang=request.target_language,
            source_is_english=request.source_is_english,
        )

        return SynthesizeResponse(
            success=True,
            cleaned_english=result["cleaned_english"],
            spoken_regional_text=result["final_spoken_text"],
            target_language=result["language"],
            voice_used=result["voice_used"],
            audio_base64=result["audio_base64"],
            audio_url=result["audio_url"],
        )

    except Exception as exc:
        logger.exception("Synthesis-JSON endpoint failed.")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc


# -----------------------------------------------------------------------
# GET /voice/audio/{filename}  (serve temporary files)
# -----------------------------------------------------------------------

@router.get("/audio/{filename}", tags=["Voice & Language"])
async def get_audio_file(filename: str):
    """Serve a previously generated temporary audio file by filename."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = language_service.audio_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found or already deleted.")

    return FileResponse(str(file_path), media_type="audio/mpeg")
