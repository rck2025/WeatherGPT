# WeatherGPT Linguistic Sovereignty & Indic Voice Integration Guide

## 1. Overview & Architectural Philosophy

WeatherGPT operates on an **Indic Linguistic Sovereignty** paradigm designed to provide high-precision, low-latency meteorological information across all 22 scheduled Indian languages (Eighth Schedule of the Constitution of India) plus English.

### Key Architectural Pillars:
1. **Whisper Nudge System**: Eliminates cold-start transcription confusion by seeding Whisper's decoder with domain and script context (`initial_prompt`) tailored to the selected target language.
2. **Multi-Stage Language Identification (LID)**: When "Auto" is selected, the engine queries Whisper's candidate language probability distribution, cross-references it with `langid` n-gram classification, and applies lexical marker disambiguation (e.g., distinguishing Marathi `आहे` / `का` / `कसे` from Hindi `है` / `क्या` / `कैसा`).
3. **Universal Indian Script Normalizer**: Eliminates `SCRIPT_MISMATCH` errors by evaluating Unicode characters at the **Script Family** level (`SCRIPT_FAMILIES`). All Devanagari languages (Marathi, Hindi, Konkani, Sanskrit, Nepali, Bodo, Dogri, Maithili) share the unified block `\u0900-\u097F` without discriminatory sub-range rejections.
4. **CJK & Foreign Hallucination Shield**: Strictly intercepts and rejects out-of-domain East Asian (Chinese, Japanese, Korean) or non-Indic hallucinations produced by speech recognition engines on audio noise (`SYS_VOICE > ERROR: SCRIPT_MISMATCH`).
5. **Acoustic De-noising Pre-processor**: Filters conversational fillers (`uh`, `um`, `ah`, `अह`) and non-lexical acoustic markers (`[breathing]`, `(sigh)`, `[laughter]`, `*cough*`) prior to translation and RAG semantic parsing.
6. **Dynamic Output Realignment**: Seamlessly aligns Edge-TTS synthesis and the frontend UI selector with the detected speech language code (`detected_lang_code`), preventing misaligned English fallbacks.
7. **Phonetic Fallback Matrix**: If an Indian language lacks a dedicated neural voice in Edge-TTS, it automatically routes to a phonetically aligned Indic sibling voice rather than crashing or falling back to English.

---

## 2. 22 Scheduled Indian Languages Matrix

| ISO Code | Language Name | Script Family | Primary Neural Voice | Phonetic Fallback Voice | Sample Weather Query |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `as` | Assamese (অসমীয়া) | Bengali | `bn-IN-TanishaaNeural` | `bn-IN-TanishaaNeural` | গুৱাহাটীত আজি বৰষুণ হ'বনে? |
| `bn` | Bengali (বাংলা) | Bengali | `bn-IN-TanishaaNeural` | `hi-IN-SwaraNeural` | কলকাতায় আজকের আবহাওয়া কেমন? |
| `brx` | Bodo (बड़ो) | Devanagari | `hi-IN-SwaraNeural` | `hi-IN-SwaraNeural` | कक्राझाराव दिनै अखा हागोन ना? |
| `doi` | Dogri (डोगरी) | Devanagari | `hi-IN-SwaraNeural` | `hi-IN-SwaraNeural` | जम्मू च आज मौसम केंह् ऐ? |
| `gu` | Gujarati (ગુજરાતી) | Gujarati | `gu-IN-DhwaniNeural` | `hi-IN-SwaraNeural` | અમદાવાદમાં આજે વરસાદ પડશે? |
| `hi` | Hindi (हिंदी) | Devanagari | `hi-IN-SwaraNeural` | `hi-IN-MadhurNeural` | दिल्ली में आज मौसम कैसा है? |
| `kn` | Kannada (ಕನ್ನಡ) | Kannada | `kn-IN-GaganNeural` | `te-IN-ShrutiNeural` | ಬೆಂಗಳೂರಿನಲ್ಲಿ ಇಂದು ಮಳೆ ಬರುತ್ತದೆಯೇ? |
| `ks` | Kashmiri (کٲشُر) | Perso-Arabic | `ur-IN-GulNeural` | `ur-IN-GulNeural` | سِریٖنَگرَس منٛز اَز روٗد پؠیہِ کیا؟ |
| `kok` | Konkani (कोंकणी) | Devanagari | `mr-IN-AarohiNeural` | `mr-IN-AarohiNeural` | पणजेत आयज पावस पडटलो काय? |
| `mai` | Maithili (मैथिली) | Devanagari | `hi-IN-SwaraNeural` | `hi-IN-SwaraNeural` | पटना में आई मौसम कोना अछि? |
| `ml` | Malayalam (മലയാളം) | Malayalam | `ml-IN-SobhanaNeural` | `ta-IN-PallaviNeural` | കൊച്ചിയിൽ ഇന്ന് മഴ പെയ്യുമോ? |
| `mni` | Manipuri (মৈতৈলোন্) | Bengali / Meitei | `bn-IN-TanishaaNeural` | `bn-IN-TanishaaNeural` | ইম্ফালদা ঙসি নোং চুরব্রা? |
| `mr` | Marathi (मराठी) | Devanagari | `mr-IN-AarohiNeural` | `hi-IN-SwaraNeural` | पुण्यात आज पाऊस पडेल का? |
| `ne` | Nepali (नेपाली) | Devanagari | `ne-NP-HemkalaNeural` | `hi-IN-SwaraNeural` | काठमाडौंमा आज मौसम कस्तो छ? |
| `or` | Odia (ଓଡ଼ିଆ) | Odia | `hi-IN-SwaraNeural` | `bn-IN-TanishaaNeural` | ଭୁବନେଶ୍ୱରରେ ଆଜି ବର୍ଷା ହେବ କି? |
| `pa` | Punjabi (ਪੰਜਾਬੀ) | Gurmukhi | `pa-IN-OjasNeural` | `hi-IN-SwaraNeural` | ਅੰਮ੍ਰਿਤਸਰ ਵਿੱਚ ਅੱਜ ਮੀਂਹ ਪਵੇਗਾ? |
| `sa` | Sanskrit (संस्कृतम्) | Devanagari | `hi-IN-SwaraNeural` | `hi-IN-SwaraNeural` | अद्य वृष्टिः भविष्यति वा? |
| `sat` | Santali (ᱥᱟᱱᱛᱟᱲᱤ) | Ol Chiki | `hi-IN-SwaraNeural` | `bn-IN-TanishaaNeural` | ᱛᱮᱦᱮᱧ ᱫᱟᱜ ᱦᱤᱡᱩᱜᱼᱟ ᱥᱮ? |
| `sd` | Sindhi (سنڌي) | Perso-Arabic | `ur-IN-GulNeural` | `ur-IN-GulNeural` | اڄ موسم ڪيئن آهي؟ |
| `ta` | Tamil (தமிழ்) | Tamil | `ta-IN-PallaviNeural` | `te-IN-ShrutiNeural` | சென்னையில் இன்று மழை பெய்யுமா? |
| `te` | Telugu (తెలుగు) | Telugu | `te-IN-ShrutiNeural` | `ta-IN-PallaviNeural` | హైదరాబాద్‌లో ఈరోజు వర్షం పడుతుందా? |
| `ur` | Urdu (اردو) | Perso-Arabic | `ur-IN-GulNeural` | `hi-IN-SwaraNeural` | لکھنؤ میں آج کا موسم کیسا ہے؟ |
| `en` | English | Latin | `en-IN-NeerjaExpressiveNeural`| `en-IN-PrabhatNeural` | Will it rain in Mumbai today? |

---

## 3. Universal Indian Script Normalizer

### The Problem in Legacy Architectures
Earlier implementations defined independent Unicode subsets for Hindi and Marathi, or checked languages sequentially and executed `break` on the first Devanagari match. This caused:
1. Marathi input to be identified as Hindi (`hi`).
2. Script alignment checks with `expected_lang="mr"` to reject the Devanagari input with `SCRIPT_MISMATCH`.

### The Universal Solution
The normalizer groups scripts into canonical **Script Families**:

```python
SCRIPT_FAMILIES: dict[str, list[tuple[int, int]]] = {
    "Devanagari":   [(0x0900, 0x097F), (0xA8E0, 0xA8FF), (0x1CD0, 0x1CFF)],
    "Bengali":      [(0x0980, 0x09FF)],
    "Gurmukhi":     [(0x0A00, 0x0A7F)],
    "Gujarati":     [(0x0A80, 0x0AFF)],
    "Odia":         [(0x0B00, 0x0B7F)],
    "Tamil":        [(0x0B80, 0x0BFF)],
    "Telugu":       [(0x0C00, 0x0C7F)],
    "Kannada":      [(0x0C80, 0x0CFF)],
    "Malayalam":    [(0x0D00, 0x0D7F)],
    "Perso-Arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "Ol Chiki":     [(0x1C50, 0x1C7F)],
    "Meitei Mayek": [(0xABC0, 0xABFF), (0xAAE0, 0xAAFF)],
    "Latin":        [(0x0020, 0x007E), (0x00A0, 0x00FF)],
}
```

### Script Purity & CJK Detection
- **Purity Calculation**: The ratio of characters belonging to the target script family over total non-whitespace/non-punctuation characters.
- **CJK Hallucination Defense**:
```python
CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Extension A
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0xAC00, 0xD7AF),   # Hangul Syllables
]
```
If any CJK characters are detected when an Indic script was expected, `validate_script_alignment` immediately returns `False` with `SYS_VOICE > ERROR: SCRIPT_MISMATCH`.

---

## 4. Whisper Nudge System & Multi-Stage LID

### Pipeline Execution Flow

```
User Voice Input (WebM / WAV)
       │
       ▼
FFmpeg Audio Normalization (16kHz, mono, s16le)
       │
       ▼
Language Selection Mode?
   ├─► Explicit Language (e.g. "mr"):
   │      Whisper transcribed with:
   │         - language = "mr"
   │         - initial_prompt = WEATHER_INITIAL_PROMPTS["mr"]
   │
   └─► Auto-Detect ("auto"):
          1. Whisper transcribe with language=None
          2. Extract candidate language probabilities
          3. Cross-verify with langid.classify(transcribed_text)
          4. Lexical Disambiguation (detect Marathi/Hindi/Nepali keywords)
       │
       ▼
Input De-noising Pre-processor
   (Removes [breathing], (sigh), uh, um, अह, etc.)
       │
       ▼
RAG Brain Ingestion & Translation
       │
       ▼
Output Realignment
   (Edge-TTS synthesizes using detected_lang; UI updates #languageSelect)
```

### Lexical Disambiguation Heuristics
When text falls within the Devanagari script family, lexical disambiguation inspects dialect-specific markers:
- **Marathi (`mr`)**: `आहे`, `आहेत`, `नाही`, `कसे`, `काय`, `पाऊस`, `हवामान`, `पुण्यात`, `मुंबईत`, `उद्या`.
- **Nepali (`ne`)**: `छ`, `छन्`, `छैन`, `कस्तो`, `पानी`, `मौसम`, `काठमाडौं`.
- **Hindi (`hi`)**: Default Devanagari fallback or explicitly verified via `langid`.

---

## 5. Acoustic De-noising Pre-processor

Speech recognition models frequently produce acoustic noise tokens on breaths, pauses, or hesitations. The pre-processor runs before text is forwarded to the RAG Brain:

```python
NON_LEXICAL_SOUNDS = [
    r"\[breathing\]", r"\[sigh\]", r"\[groan\]", r"\[gasp\]",
    r"\[laughter\]", r"\[cough\]", r"\[throat-clearing\]",
    r"\(sigh\)", r"\(breathing\)", r"\(laughter\)", r"\(cough\)",
    r"\*sigh\*", r"\*cough\*", r"\*laughter\*",
]

FILLERS = [
    r"\buh\b", r"\bum\b", r"\bah\b", r"\ber\b", r"\bhm\b", r"\bhmm\b",
    r"\bअह\b", r"\bउम\b", r"\bआह\b",
]
```

---

## 6. Real-Time Speech Synthesis & Phonetic Fallback

Edge-TTS neural voice synthesis applies primary regional voices. If Edge-TTS reports that a voice is unavailable or fails during real-time streaming, the synthesis engine invokes `get_phonetic_fallback_voice(target_lang)` and re-attempts generation:

```python
# Phonetic fallback attempt:
fallback_voice = get_phonetic_fallback_voice(target_lang)
if fallback_voice and fallback_voice != chosen_voice:
    logger.info("Retrying speech synthesis with phonetic fallback voice: %s", fallback_voice)
    communicate = edge_tts.Communicate(spoken_text, fallback_voice)
    await communicate.save(str(filepath))
```

This ensures guaranteed delivery of audible speech in an Indic accent without falling back to English.

---

## 7. Open Source & Bhashini Compliance

All components in WeatherGPT are 100% open source and compatible with Government of India **Digital India Bhashini ULCA** specifications:
- **ASR**: `faster-whisper` (open-source local quantized inference) with Bhashini ULCA API compatibility hooks.
- **TTS**: Microsoft Edge-TTS neural voices (open protocol) with Bhashini Indic TTS fallback pathways.
- **LID**: `langid.py` (open source naive Bayes classifier) combined with Unicode script family analysis.
