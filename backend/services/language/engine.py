"""
WeatherHybridEngine — core voice processing engine.

Combines:
  - FFmpeg audio standardisation (format-agnostic ingestion)
  - Faster-Whisper (offline CPU STT + language detection)
  - Bhashini API translation with deep-translator fallback
  - Microsoft Edge-TTS neural speech synthesis for 10 Indian regional languages

Sourced and adapted from SOHAM-DEV2/WeatherGPT-MK1 (feature/voice-integrated-v1).
"""
import logging
import os
import subprocess
import requests

from backend.services.audio_utils import standardize_audio
from backend.services.language.bhashini_asr import (
    BHASHINI_ASR_SUPPORTED_LANGUAGES,
    bhashini_transcribe,
)
from backend.services.language.cleaner import (
    clean_bot_response,
    clean_transcribed_input,
    expand_units_for_language,
    get_phonetic_fallback_voice,
    get_voice_for_language,
    safe_translate,
)
from backend.services.language.resolver import SCRIPT_REGISTRY, validate_script_alignment

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Top 5+ Weather Keywords in Native Script for Whisper Acoustic Priming
# (Primes Whisper to recognize phonemes and ignore background noise/gibberish)
# -----------------------------------------------------------------------
WEATHER_INITIAL_PROMPTS: dict[str, str] = {
    "hi": "मौसम, बारिश, तापमान, चक्रवात, आंधी, हवा, बाढ़, पूर्वानुमान, दिल्ली, लखनऊ",
    "bn": "বৃষ্টি, আবহাওয়া, ঘূর্ণিঝড়, কলকাতা, বন্যা, তাপমাত্রা, পূর্বাভাস, ঝড়, কালবৈশাখী, নদী, মেঘ",
    "ta": "வானிலை, மழை, புயல், சென்னை, வெப்பநிலை, காற்று, சூறாவளி, முன்னறிவிப்பு, வெள்ளம்",
    "te": "వాతావరణం, వర్షం, తుఫాను, హైదరాబాద్, ఉష్ణోగ్రత, గాలి, వరదలు, సూచన, మేఘాలు",
    "mr": "पाऊस, हवामान, वादळ, मुंबई, पुणे, चक्रीवादळ, तापमान, वारा, अंदाज, पाऊस पडेल का, ढग",
    "gu": "હવામાન, વરસાદ, વાવાઝોડું, તાપમાન, પવન, પૂર, આગાહી, અમદાવાદ",
    "kn": "ಹವಾಮಾನ, ಮಳೆ, ಚಂಡಮಾರುತ, ತಾಪಮಾನ, ಗಾಳಿ, ಮುನ್ಸೂಚನೆ, ಬೆಂಗಳೂರು",
    "ml": "കാലാവസ്ഥ, മഴ, ചുഴലിക്കാറ്റ്, കൊച്ചി, തിരുവനന്തപുരം, താപനില, കാറ്റ്, പ്രവചനം",
    "ur": "موسم, بارش, طوفان, درجہ حرارت, ہوا, سیلاب, پیش گوئی",
    "pa": "ਮੌਸਮ, ਮੀਂਹ, ਤੂਫ਼ਾਨ, ਤਾਪਮਾਨ, ਹਵਾ, ਹੜ੍ਹ, ਭਵਿੱਖਬਾਣੀ",
    "or": "ପାଣିପାଗ, ବର୍ଷା, ବାତ୍ୟା, ତାପମାତ୍ରା, ପବନ, ବନ୍ୟା, ପୂର୍ବାନୁମାନ, ଭୁବନେଶ୍ୱର",
    "as": "বতৰ, বৰষুণ, ধুমুহা, উষ্ণতা, বতাহ, বানপানী, আগজাননী, গুৱাহাটী",
    "ne": "मौसम, वर्षा, चक्रवात, तापक्रम, हावा, बाढी, पूर्वानुमान",
    "sa": "ऋतुः, वृष्टिः, वात्या, तापमानम्, वायुः, मेघः, सूचना",
    "kok": "हवामान, पावस, वादळ, तापमान, वारो, अंदाज",
    "mai": "मौसम, बरखा, तापमान, आंधी, हवा, पूर्वानुमान",
    "brx": "बथोर, अखा, बार, सानदुं, सानाय",
    "doi": "मौसम, बरखा, तपत, हवा, झक्खड़",
    "ks": "موسم, رُود, طوفان, حرارت, واو",
    "sd": "موسم, برسات, طوفان, گرمي پد, هوا",
    "sat": "ᱦᱚᱭ-ᱦᱤᱥᱤᱫ, ᱫᱟᱜ, ᱦᱚᱭ, ᱞᱚᱞᱚ",
    "mni": "নোংশা-নুংশিত, নোং, নুংশিত, অশাবা",
    "en": "weather, rain, cyclone, temperature, wind, flood, forecast, thunderstorm",
}


# -----------------------------------------------------------------------
# Acoustic Language Token Mapping for Faster-Whisper
# Maps non-standard / unsupported ISO codes to optimal acoustic models
# (Whisper has 99 language tokens; kok, mai, brx, doi, ks, mni, sat, or
# are mapped to their closest linguistic acoustic surrogate or auto-detect with prompt)
# -----------------------------------------------------------------------
WHISPER_LANGUAGE_CODE_MAP: dict[str, str | None] = {
    "en": "en", "hi": "hi", "bn": "bn", "ta": "ta", "te": "te", "mr": "mr",
    "gu": "gu", "kn": "kn", "ml": "ml", "pa": "pa", "ur": "ur", "as": "as",
    "ne": "ne", "sa": "sa", "sd": "sd",
    "kok": "mr",  # Konkani -> Marathi acoustic Devanagari model
    "mai": "hi",  # Maithili -> Hindi acoustic model
    "doi": "hi",  # Dogri -> Hindi acoustic model
    "brx": "hi",  # Bodo -> Hindi acoustic model
    "ks":  "ur",  # Kashmiri -> Urdu acoustic Perso-Arabic model
    "mni": "bn",  # Manipuri -> Bengali acoustic model
    "sat": "hi",  # Santali -> Hindi acoustic model
    "or":  None,  # Odia -> Auto-detect with Odia initial prompt (no <|or|> token in Whisper)
}


# -----------------------------------------------------------------------
# Hybrid Voice Engine
# -----------------------------------------------------------------------

class WeatherHybridEngine:
    """
    Unified voice engine for WeatherGPT:

    - Format-agnostic audio ingestion (16 kHz Mono WAV via FFmpeg)
    - Fast offline STT with Faster-Whisper (int8 CPU) with Dynamic Initial Prompts
    - Nudge System for User-Selected Languages & Multi-Stage LID for Auto-Detect
    - Input De-Noising Pre-processor (removes fillers, non-lexical sounds, and breathing)
    - Universal Indian Script Normalizer validation (agnostic Devanagari & regional scripts)
    - Hybrid translation: Bhashini Cloud → deep-translator fallback
    - Microsoft Edge-TTS neural speech synthesis with phonetic fallbacks across 22 languages
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        logger.info("Initialising WeatherHybridEngine (%s on %s)…", model_size, device)

        # Lazy import so the server starts fast even when faster-whisper isn't installed yet
        try:
            from faster_whisper import WhisperModel  # type: ignore
            self._stt_model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except ImportError:
            logger.warning("faster-whisper not installed; STT transcription will be unavailable.")
            self._stt_model = None

        # Bhashini credentials (official Digital India MeitY ULCA Gateway)
        self._bhashini_user_id = os.getenv("BHASHINI_USER_ID", "135c3e6980-4b41-4cc5-91ce-dc3a356cf841")
        self._bhashini_api_key = os.getenv("BHASHINI_API_KEY")
        self._bhashini_url = os.getenv(
            "BHASHINI_INFERENCE_URL",
            "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
        )

    # ------------------------------------------------------------------
    # Public: STT (Speech-To-Text)
    # ------------------------------------------------------------------

    def process_query(
        self,
        audio_path: str,
        target_lang: str | None = None,
        language_hint: str | None = None,
        user_language: str | None = None,
    ) -> dict:
        """
        Deterministic Linguistic Sovereignty Voice Ingestion:
        1. Standardise incoming audio to 16 kHz Mono WAV.
        2. UI Dropdown is the Single Source of Truth (SSoT):
           Transcribe with Faster-Whisper using explicit target_lang (auto-detect disabled).
        3. If no speech is detected, raise SYS_VOICE > NO_SIGNAL.
        4. Clean non-lexical filler noise.
        5. Translate regional query to English for LLM/RAG consumption.

        Returns:
            {
                "original_text": str,
                "detected_lang": str,   # Verified ISO 639-1 code e.g. "ur", "bn", "mr", "hi"
                "confidence":    float,
                "english_query": str,
                "transcription_method": str,
                "transcription_source": str,
                "locked_language_code": str,
            }
        """
        if self._stt_model is None:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: .venv/bin/pip install faster-whisper"
            )
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path!r}")

        optimised = standardize_audio(audio_path)
        logger.debug("Whisper: transcribing %s (target_lang=%s, hint=%s, user_lang=%s)…", optimised, target_lang, language_hint, user_language)

        # Explicit Language Routing: Prioritize target_lang, then user_language, then language_hint
        effective_lang = target_lang or user_language or language_hint or "en"
        raw_hint = (effective_lang or "en").strip().lower()
        is_auto = raw_hint in ("", "auto", "none")
        norm_lang = "en" if is_auto else raw_hint.split("-")[0].split("_")[0]

        user_text = ""
        user_lang = norm_lang
        confidence = 0.0
        info = None
        transcription_method = "Whisper"

        try:
            if not is_auto and norm_lang:
                # -------------------------------------------------------------
                # TASK 1: Force Explicit Language Routing (Deterministic SSoT)
                # Auto-Detect is strictly DISABLED when user specifies a language.
                # Whisper is instructed to use language-specific neural weights.
                # -------------------------------------------------------------
                nudge_prompt = WEATHER_INITIAL_PROMPTS.get(norm_lang, WEATHER_INITIAL_PROMPTS.get("en", ""))
                whisper_target = WHISPER_LANGUAGE_CODE_MAP.get(norm_lang, norm_lang)
                transcribe_kwargs = {
                    "beam_size": 5,
                    "language": whisper_target,
                    "initial_prompt": nudge_prompt,
                }
                logger.info(
                    "🎯 [DETERMINISTIC ROUTING] Explicit target_lang='%s' locked as SSoT (Whisper acoustic lang='%s'). Auto-detect disabled.",
                    norm_lang,
                    whisper_target,
                )
                try:
                    segments, info = self._stt_model.transcribe(optimised, **transcribe_kwargs)
                except ValueError as val_err:
                    logger.warning(
                        "Whisper acoustic model does not recognize language '%s': %s. Retrying with auto language and initial prompt...",
                        whisper_target,
                        val_err,
                    )
                    transcribe_kwargs["language"] = None
                    segments, info = self._stt_model.transcribe(optimised, **transcribe_kwargs)

                user_text = " ".join(s.text for s in segments).strip()
                user_lang = norm_lang
                confidence = float(info.language_probability) if (info and hasattr(info, "language_probability") and info.language_probability is not None) else 0.95

                # TASK 4: Real Bhashini Fallback if Whisper returns empty text or low confidence (< 0.70)
                is_low_conf = (confidence < 0.70) or (not user_text)
                if is_low_conf and norm_lang in BHASHINI_ASR_SUPPORTED_LANGUAGES:
                    logger.info(
                        "🔄 [BHASHINI FALLBACK] Whisper returned low confidence (%.2f < 0.70) or empty text for '%s'. Awaiting Bhashini ASR...",
                        confidence, norm_lang,
                    )
                    bhashini_res = bhashini_transcribe(optimised, target_lang=norm_lang)
                    if bhashini_res and bhashini_res.get("text"):
                        user_text = bhashini_res["text"].strip()
                        confidence = float(bhashini_res.get("confidence", 0.95))
                        transcription_method = "Bhashini"
                        logger.info(
                            "💎 [BHASHINI SUCCESS] Overwrote transcription via Bhashini: '%s' (conf=%.2f)",
                            user_text, confidence,
                        )
            else:
                # -------------------------------------------------------------
                # Auto-Detect mode (Only run when user explicitly selects auto)
                # -------------------------------------------------------------
                segments, info = self._stt_model.transcribe(optimised, beam_size=5, language=None)
                user_text = " ".join(s.text for s in segments).strip()

                top_candidates = []
                if info and hasattr(info, "all_language_probs") and info.all_language_probs:
                    top_candidates = [lang for lang, _prob in info.all_language_probs[:3]]
                elif info and info.language:
                    top_candidates = [info.language]

                whisper_lang = (info.language if info else "en").split("-")[0].lower()
                confidence = float(info.language_probability) if (info and hasattr(info, "language_probability") and info.language_probability is not None) else 0.0

                from backend.services.language.resolver import detect_dominant_script
                script_lang, script_name, script_purity = detect_dominant_script(user_text)

                logger.info(
                    "Multi-Stage LID: Whisper=%s (top3=%s, conf=%.2f), ScriptDetector=%s (%s, purity=%.2f)",
                    whisper_lang, top_candidates, confidence, script_lang, script_name, script_purity
                )

                if script_lang != "en" and script_purity >= 0.20:
                    user_lang = script_lang
                elif whisper_lang in SCRIPT_REGISTRY:
                    user_lang = whisper_lang
                else:
                    user_lang = script_lang or "en"

                is_low_conf = (confidence < 0.50) or (not user_text)
                target_fallback = user_lang if user_lang in BHASHINI_ASR_SUPPORTED_LANGUAGES else (
                    top_candidates[0] if top_candidates and top_candidates[0] in BHASHINI_ASR_SUPPORTED_LANGUAGES else "hi"
                )

                if is_low_conf and target_fallback in BHASHINI_ASR_SUPPORTED_LANGUAGES:
                    bhashini_res = bhashini_transcribe(optimised, target_lang=target_fallback)
                    if bhashini_res and bhashini_res.get("text"):
                        user_text = bhashini_res["text"].strip()
                        confidence = float(bhashini_res.get("confidence", 0.95))
                        transcription_method = "Bhashini"
                        user_lang = bhashini_res.get("detected_lang", target_fallback)

        finally:
            if optimised != audio_path and os.path.exists(optimised):
                try:
                    os.remove(optimised)
                except OSError:
                    pass

        # -----------------------------------------------------------------
        # Task 1 Empty Speech Guard: Return SYS_VOICE > NO_SIGNAL
        # -----------------------------------------------------------------
        if not user_text or not user_text.strip():
            logger.warning("SYS_VOICE > NO_SIGNAL: No clear speech detected.")
            raise RuntimeError("SYS_VOICE > NO_SIGNAL: No clear speech detected.")

        # -----------------------------------------------------------------
        # Input De-Noising Pre-processor
        # Removes filler words and non-lexical sounds (uh, ah, breathing, etc.)
        # -----------------------------------------------------------------
        cleaned_input = clean_transcribed_input(user_text)
        if cleaned_input:
            user_text = cleaned_input

        # SIH Demo Monitoring Log
        logger.info(
            "🎯 [SIH MONITOR] Method: %s | Confidence: %.2f (%.1f%%) | Locked Lang: %s | Text: '%s'",
            transcription_method, confidence, confidence * 100, user_lang, user_text,
        )

        # NOTE: validate_script_alignment is PURGED from the voice ingestion loop.
        # Deterministic Linguistic Sovereignty ensures speech is never rejected due to script mismatch.

        english_text = self.translate(user_text, source_lang=user_lang, target_lang="en")

        return {
            "original_text": user_text,
            "detected_lang": user_lang,
            "confidence":    confidence,
            "english_query": english_text,
            "transcription_method": transcription_method,
            "transcription_source": transcription_method,
            "locked_language_code": user_lang,
        }

    transcribe = process_query

    # ------------------------------------------------------------------
    # Public: Translation
    # ------------------------------------------------------------------

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate *text* from *source_lang* to *target_lang*.
        Tries Bhashini first (if credentials are configured), then falls
        back to the deep-translator multi-engine chain.
        """
        if not text:
            return text

        src = source_lang.split("-")[0].lower()
        tgt = target_lang.split("-")[0].lower()

        if src == tgt:
            return text

        if self._bhashini_user_id and self._bhashini_api_key:
            try:
                result = self._bhashini_translate(text, src, tgt)
                if result and result != text:
                    return result
            except Exception as exc:
                logger.debug("Bhashini skipped: %s", exc)

        return safe_translate(text, source_lang=src, target_lang=tgt)

    # ------------------------------------------------------------------
    # Public: TTS
    # ------------------------------------------------------------------

    async def generate_regional_response(
        self,
        raw_response: str,
        target_lang: str = "hi",
        output_file: str = "weather_response.mp3",
        source_is_english: bool = True,
    ) -> dict:
        """
        End-to-end voice synthesis pipeline:
        1. Strip LLM noise (markdown, thinking tags, emojis, filler).
        2. Translate clean English text into the target regional language.
        3. Expand meteorological units into natural spoken regional words.
        4. Synthesise neural audio with Microsoft Edge-TTS.

        Returns:
            {
                "cleaned_english":   str,
                "final_spoken_text": str,
                "language":          str,
                "voice_used":        str,
                "output_file":       str,
            }
        """
        try:
            import edge_tts  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed. Run: .venv/bin/pip install edge-tts"
            ) from exc

        if not target_lang or target_lang.strip().lower() in ("auto", "none", ""):
            raise ValueError("Linguistic Lock: Explicit target_lang required for voice synthesis, 'auto' is prohibited.")

        norm_lang = target_lang.split("-")[0].lower()

        # Step 1 & 2 — clean raw English LLM output and translate if source is English
        if source_is_english:
            cleaned_en = clean_bot_response(raw_response, lang_code="en")
            if norm_lang != "en":
                regional_text = self.translate(cleaned_en, source_lang="en", target_lang=norm_lang)
            else:
                regional_text = cleaned_en
        else:
            cleaned_en = raw_response
            regional_text = raw_response

        # Step 3 — regional speech polish (unit expansion + spacing)
        final_spoken = clean_bot_response(regional_text, lang_code=norm_lang)

        # Step 4 — pick neural voice and apply Pre-Synthesis Script Check (Task 5)
        voice_name = get_voice_for_language(norm_lang)
        from backend.services.language.cleaner import VoiceCleaner
        voice_name, norm_lang = VoiceCleaner.sanitize_voice_for_script(
            voice_name=voice_name,
            text=final_spoken,
            target_lang=norm_lang,
        )

        # Step 4.5 — Odia phonetic Devanagari conversion for Edge-TTS
        # Edge-TTS lacks an Odia neural voice and rejects raw Odia script (\u0B00-\u0B7F).
        # SwaraNeural (hi-IN-SwaraNeural) synthesizes phonetic Devanagari with authentic Odia phonetics.
        if norm_lang == "or" or any(0x0B00 <= ord(c) <= 0x0B7F for c in final_spoken):
            from backend.services.language.cleaner import odia_to_phonetic_devanagari
            final_spoken = odia_to_phonetic_devanagari(final_spoken)

        try:
            communicate = edge_tts.Communicate(final_spoken, voice_name)
            await communicate.save(output_file)
        except Exception as tts_err:
            fallback_voice = get_phonetic_fallback_voice(norm_lang)

            logger.warning(
                "Edge-TTS primary voice '%s' failed (%s). Retrying with phonetic fallback voice '%s'...",
                voice_name, tts_err, fallback_voice
            )
            if norm_lang == "or" or any(0x0B00 <= ord(c) <= 0x0B7F for c in final_spoken):
                from backend.services.language.cleaner import odia_to_phonetic_devanagari
                final_spoken = odia_to_phonetic_devanagari(final_spoken)
            try:
                communicate = edge_tts.Communicate(final_spoken, fallback_voice)
                await communicate.save(output_file)
                voice_name = fallback_voice
            except Exception as fb_err:
                logger.error("Edge-TTS phonetic fallback voice '%s' also failed: %s", fallback_voice, fb_err)
                raise fb_err

        return {
            "cleaned_english":   cleaned_en,
            "final_spoken_text": final_spoken,
            "language":          norm_lang,
            "voice_used":        voice_name,
            "output_file":       output_file,
        }

    # ------------------------------------------------------------------
    # Private: Bhashini helper
    # ------------------------------------------------------------------

    def _bhashini_translate(self, text: str, source: str, target: str) -> str:
        try:
            from backend.services.language.translator import bhashini_translate
            return bhashini_translate(text, source_lang=source, target_lang=target)
        except Exception as exc:
            logger.warning("Bhashini translation in engine failed: %s", exc)
            return text
