"""
Acoustic Shielding & Audio Pre-processing for WeatherGPT Voice Engine.

Implements:
1. Dynamic Gain Control & Peak Normalization to -0.1 dB (loudnorm True Peak = -0.1).
2. Noise Gate & Acoustic Filtering:
   - High-pass filter at 200 Hz: strips low-frequency hums, mic thumps, air conditioners.
   - Low-pass filter at 3000 Hz: removes high-frequency static and sibilance common in phone mics.
   - afftdn: FFT-based audio denoiser / noise gate.
3. 16 kHz Mono WAV format conversion optimal for speech recognition (Whisper & Bhashini).
"""

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

_FFMPEG_PATH: str | None = None


def _get_ffmpeg_path() -> str | None:
    global _FFMPEG_PATH
    if _FFMPEG_PATH and os.path.exists(_FFMPEG_PATH):
        return _FFMPEG_PATH

    resolved = shutil.which("ffmpeg")
    if resolved:
        _FFMPEG_PATH = resolved
        return _FFMPEG_PATH

    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"),
        os.path.expanduser(r"~\scoop\shims\ffmpeg.exe"),
    ]
    for path in common_paths:
        if os.path.isfile(path):
            _FFMPEG_PATH = path
            os.environ["PATH"] = os.path.dirname(path) + os.pathsep + os.environ.get("PATH", "")
            return _FFMPEG_PATH

    return None


def standardize_audio(input_path: str, output_path: str | None = None) -> str:
    """
    Apply acoustic shielding and standardize any browser audio file
    (webm, ogg, wav, mp3, m4a) to a 16 kHz Mono WAV file.

    Audio Filters Applied:
    - `highpass=f=200`: Cuts low-frequency room rumbles, vehicle noise, and mic thumps.
    - `lowpass=f=3000`: Cuts frequencies above the human vocal formants, eliminating hiss.
    - `afftdn`: FFT audio noise reduction filter for active background suppression.
    - `loudnorm=I=-16:TP=-0.1:LRA=11`: EBU R128 integrated loudness normalization with
      True Peak clamped to -0.1 dB, giving consistent volume regardless of distance from mic.

    If FFmpeg is unavailable or an error occurs, falls back to graceful degradation.
    """
    if not os.path.exists(input_path):
        return input_path

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_shielded.wav"

    ffmpeg_bin = _get_ffmpeg_path() or "ffmpeg"

    # Acoustic shielding filter chain with -0.1 dB True Peak normalization
    filter_chain = "highpass=f=200,lowpass=f=3000,afftdn,loudnorm=I=-16:TP=-0.1:LRA=11"

    cmd = [
        ffmpeg_bin, "-i", input_path,
        "-af", filter_chain,
        "-ar", "16000",
        "-ac", "1",
        output_path, "-y",
    ]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=30,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.warning(
            "Acoustic shielding filter chain failed (%s); trying standard resampling fallback.",
            exc,
        )
        # Fallback to basic resampling without complex filters
        fallback_cmd = [
            ffmpeg_bin, "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            output_path, "-y",
        ]
        try:
            subprocess.run(
                fallback_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=30,
            )
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        except Exception as fb_exc:
            logger.warning("Basic FFmpeg audio conversion failed (%s); using original audio.", fb_exc)

    return input_path
