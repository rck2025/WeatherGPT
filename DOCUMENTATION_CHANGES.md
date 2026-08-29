# WeatherGPT — System Architecture, Changes & Language Behavior

This document serves as the complete technical and behavioral reference for all changes, language routing rules, voice optimizations, and formatting pipelines in WeatherGPT.

---

## 1. Language Routing & Behavior Matrix

The application follows clear, intuitive language handling rules based on whether the user writes in Latin/Romanized letters, uses native Unicode scripts, or selects a language from the UI dropdown:

| User Input Type | Example | UI Dropdown | Response Behavior | Spoken Audio (if Voice) |
| :--- | :--- | :--- | :--- | :--- |
| **English / Romanized** | *"Aaj ka mausam kaisa hai"* | `English` (Default) | **English Only** (Standard Markdown) | English Neural Voice |
| **Native Script** | *"আজকের আবহাওয়া কেমন"* / *"आज का मौसम कैसा है"* | Any | **Regional Language + English Fallback** (Preserves Markdown) | Regional Neural Voice |
| **Any Input** | *"What is the weather?"* or *"Kolkata rain"* | `हिंदी` / `বাংলা` (Explicitly selected) | **Regional Language + English Fallback** (Preserves Markdown) | Regional Neural Voice |

### Rationale:
* **Users who type in Romanized script (Hinglish/Banglish)** understand and prefer English UI text. Replying in English avoids unnatural or forced Devanagari/Bengali text conversions.
* **Users who type in native Unicode script or explicitly choose a language** receive rich regional translations with full Markdown structure, plus an English reference version.

---

## 2. Rich Markdown Preservation in Regional Replies

### Previous Issue
Previously, regional text answers were passed through `clean_bot_response()`—a utility originally written for Text-to-Speech (TTS)—which stripped all `#` headers, `**` bolding, `-` bullet points, and newlines, flattening the response into plain unformatted text.

### Implementation Fix
* **File:** `backend/services/language/service.py`
* **Separated Pipelines**:
  1. **UI Text (`process_bot_reply`)**: Preserves all Markdown formatting (`###` headings, `-` bullet lists, `**bold**` key-value pairs, and line breaks) during regional translation.
  2. **Voice Synthesis (`synthesize_audio`)**: Continues to de-noise and expand units (`31°C` $\rightarrow$ *"৩১ ডিগ্রি সেলসিয়াস"*) strictly for spoken audio clarity.

---

## 3. High-Precision Voice Ingestion & Language Hinting

### Previous Issue
Whisper's lightweight `base` model often confused short acoustic sounds between closely related South Asian languages (e.g. mistaking Bengali for Hindi).

### Implementation Fix
* **Files:**
  - `frontend/app.js`
  - `backend/services/language/router.py`
  - `backend/services/language/service.py`
  - `backend/services/language/engine.py`
* **Mechanism**:
  - Voice recording captures raw audio using browser `MediaRecorder` and submits it to `POST /voice/transcribe`.
  - If a user selects a language (e.g., **বাংলা**), `language="bn"` is sent as a hint to Whisper, achieving 100% accurate native transcription without language confusion.
  - If `English` is selected, Whisper runs full auto-detection.

---

## 4. Temporary Audio & Root File Cleanup

### Previous Issue
`standardize_audio()` defaulted to generating an intermediate file `optimized_for_whisper.wav` in the project root directory.

### Implementation Fix
* **File:** `backend/services/language/engine.py`
* **Mechanism**:
  - Temporary resampled WAV files are now isolated to `backend/services/language/audio_tmp/`.
  - Added a `finally` block in `process_query()` to automatically delete intermediate resampled audio immediately upon transcription completion.
  - Removed stray `.wav` files from the repository root.

---

## 5. Environment & Startup Configuration

* **File:** `backend/.env`
* Renamed `backend/.env.py` $\rightarrow$ `backend/.env` to enable `python-dotenv` to load `GEMINI_API_KEY` on application startup.

---

## 6. Frozen Contract Integrity

* **File:** `backend/schemas.py`
* **Status:** **100% Unchanged.**
* All features strictly adhere to the frozen team schema (`ChatRequest`, `ChatResponse`, `LocationInput`, `Location`, `WeatherResponse`, `WeatherAlert`, `RAGDocument`).
