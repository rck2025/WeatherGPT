"""
Speech-output de-noising, unit normalization, and voice mapping.

Sourced and adapted from SOHAM-DEV2/WeatherGPT-MK1 (feature/voice-integrated-v1).
Keeps WeatherGPT's LLM output clean and natural for regional speech synthesis.
"""
import re

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator
except ImportError:
    GoogleTranslator = None
    MyMemoryTranslator = None


# -----------------------------------------------------------------------
# Edge-TTS Neural Voice Map — 10 Indian Regional Languages
# -----------------------------------------------------------------------

REGIONAL_VOICE_MAP: dict[str, str] = {
    "hi":  "hi-IN-SwaraNeural",
    "bn":  "bn-IN-TanishaaNeural",
    "ta":  "ta-IN-PallaviNeural",
    "te":  "te-IN-ShrutiNeural",
    "mr":  "mr-IN-AarohiNeural",
    "gu":  "gu-IN-DhwaniNeural",
    "kn":  "kn-IN-SapnaNeural",
    "ml":  "ml-IN-SobhanaNeural",
    "ur":  "ur-IN-GulNeural",
    "en":  "en-IN-NeerjaExpressiveNeural",
}


# -----------------------------------------------------------------------
# Meteorological Unit Expansions per Language
# -----------------------------------------------------------------------

UNIT_EXPANSIONS: dict[str, dict[str, str]] = {
    "en": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 degrees Celsius",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 degrees Fahrenheit",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 kilometers per hour",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 meters per second",
        r"(\d+(?:\.\d+)?)%":         r"\1 percent",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 hectopascals",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 millimeters",
    },
    "hi": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 डिग्री सेल्सियस",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 डिग्री फारेनहाइट",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 किलोमीटर प्रति घंटा",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 मीटर प्रति सेकंड",
        r"(\d+(?:\.\d+)?)%":         r"\1 प्रतिशत",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 हेक्टोपास्कल",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 मिलीमीटर",
    },
    "bn": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ডিগ্রি সেলসিয়াস",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 ডিগ্রি ফারেনহাইট",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 কিলোমিটার প্রতি ঘণ্টা",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 মিটার প্রতি সেকেন্ড",
        r"(\d+(?:\.\d+)?)%":         r"\1 শতাংশ",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 হেক্টোপাস্কাল",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 মিলিমিটার",
    },
    "ta": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 டிகிரி செல்சியஸ்",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 கிலோமீட்டர் மணி வேகம்",
        r"(\d+(?:\.\d+)?)%":         r"\1 சதவீதம்",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 மில்லிமீட்டர்",
    },
    "te": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 డిగ్రీల సెల్సియస్",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 కిలోమీటర్లు గంటకు",
        r"(\d+(?:\.\d+)?)%":         r"\1 శాతం",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 మిల్లీమీటర్లు",
    },
    "mr": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 अंश सेल्सिअस",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 किलोमीटर प्रति तास",
        r"(\d+(?:\.\d+)?)%":         r"\1 टक्के",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 मिलिमीटर",
    },
    "gu": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ડિગ્રી સેલ્સિયસ",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 કિલોમીટર પ્રતિ કલાક",
        r"(\d+(?:\.\d+)?)%":         r"\1 ટકા",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 મિલીમીટર",
    },
    "kn": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ಡಿಗ್ರಿ ಸೆಲ್ಸಿಯಸ್",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 ಕಿಲೋಮೀಟರ್ ಪ್ರತಿ ಗಂಟೆ",
        r"(\d+(?:\.\d+)?)%":         r"\1 ಪ್ರತಿಶತ",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 ಮಿಲಿಮೀಟರ್",
    },
    "ml": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ഡിഗ്രി സെൽഷ്യസ്",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 കിലോമീറ്റർ പ്രതി മണിക്കൂർ",
        r"(\d+(?:\.\d+)?)%":         r"\1 ശതമാനം",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 മില്ലിമീറ്റർ",
    },
    "ur": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ڈگری سینٹی گریڈ",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 کلومیٹر فی گھنٹہ",
        r"(\d+(?:\.\d+)?)%":         r"\1 فیصد",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 ملی میٹر",
    },
}


# -----------------------------------------------------------------------
# Conversational-filler patterns to strip from LLM output
# -----------------------------------------------------------------------

FILLER_PATTERNS: list[str] = [
    r"^(?:certainly|absolutely|sure|of course|great|hello|hi there)[,!.]?\s*",
    r"^(?:here is|here's|this is)\s+(?:the\s+)?(?:latest\s+|current\s+)?(?:weather\s+)?(?:update|report|forecast)?(?:\s+for\s+(?:you|[a-zA-Z\s,]+))?[\s,!:]*",
    r"^(?:the\s+)?(?:latest|current)\s+weather\s+(?:update|report|forecast)?(?:\s+for\s+(?:you|[a-zA-Z\s,]+))?[\s,!:]*",
    r"^(?:for\s+(?:you|[a-zA-Z\s,]+))[:,\s-]*",
    r"(?:i hope this helps|let me know if you (?:have any other questions|need anything else)|have a (?:great|wonderful) day|stay safe)!?.*$",
    r"as an ai language model[,\s].*?[.!?]",
]

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff"
    r"\u2600-\u27ff"
    r"\u2300-\u23ff"
    r"\u2b50\u2b55\u2934\u2935"
    r"\u200d\ufe0f\ufe0e"
    r"]+",
    flags=re.UNICODE,
)


# -----------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------

def get_voice_for_language(lang_code: str) -> str:
    """Return the optimal Edge-TTS Neural Voice for the given ISO language code."""
    if not lang_code:
        return REGIONAL_VOICE_MAP["en"]
    norm = lang_code.strip().lower()
    if norm in REGIONAL_VOICE_MAP:
        return REGIONAL_VOICE_MAP[norm]
    short = norm.split("-")[0].split("_")[0]
    return REGIONAL_VOICE_MAP.get(short, REGIONAL_VOICE_MAP["en"])


def strip_markdown_and_artifacts(text: str) -> str:
    """Strip markdown formatting, code blocks, emojis, and citation noise."""
    if not text:
        return ""

    # thinking / CoT blocks
    text = re.sub(r"<\s*think\s*>[\s\S]*?<\s*/\s*think\s*>", "", text, flags=re.IGNORECASE)

    # code blocks and backticks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"`+", " ", text)

    # headers
    text = re.sub(r"#{1,6}", " ", text)

    # bold / italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"\*+", " ", text)
    text = re.sub(r"_+", " ", text)

    # bullet / ordered list markers
    text = re.sub(r"^\s*[-*+•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # blockquotes and horizontal rules
    text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-=_*]{3,}\s*$", "", text, flags=re.MULTILINE)

    # links and bare URLs
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)

    # bracket citations  [1], [Source: ...]
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[(?:source|note|ref)[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\((?:source|note|ref)[^\)]*\)", "", text, flags=re.IGNORECASE)

    # parenthetical clauses → comma-delimited for smoother reading
    text = re.sub(r"\(([^()]+)\)", r", \1, ", text)

    # emojis and pictographs
    text = EMOJI_PATTERN.sub(" ", text)

    # table pipes and misc symbols
    text = re.sub(r"[|~^\\<>]", " ", text)

    return text


def strip_conversational_filler(text: str) -> str:
    """Remove AI/robot preambles and boilerplate closings."""
    if not text:
        return ""
    cleaned = text.strip()
    for _ in range(2):
        for pattern in FILLER_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()
    return cleaned


def expand_units_for_language(text: str, lang_code: str = "en") -> str:
    """Expand meteorological units into natural spoken words for the target language."""
    if not text:
        return ""
    short_lang = lang_code.split("-")[0].split("_")[0].lower() if lang_code else "en"
    expansions = UNIT_EXPANSIONS.get(short_lang, UNIT_EXPANSIONS["en"])
    for pattern, replacement in expansions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    # Fallback: apply English unit replacement if raw symbols still remain
    if short_lang != "en":
        for pattern, replacement in UNIT_EXPANSIONS["en"].items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def clean_bot_response(text: str, lang_code: str = "en") -> str:
    """
    Complete de-noising pipeline for WeatherGPT LLM output:
    1. Strip thinking tags and conversational filler.
    2. Strip markdown and noise artifacts.
    3. Second-pass filler strip (post-markdown).
    4. Expand meteorological units into spoken words for the target language.
    5. Normalize spacing and punctuation for clean TTS output.
    """
    if not text or not text.strip():
        return ""

    text = strip_conversational_filler(text)
    text = strip_markdown_and_artifacts(text)
    text = strip_conversational_filler(text)
    text = expand_units_for_language(text, lang_code)

    # Normalize spacing and punctuation
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([,;:!?।])\s*", r"\1 ", text)
    text = re.sub(r"(?<!\d)\s*\.\s*(?!\d)", ". ", text)
    text = re.sub(r"[,;]\s*[,;]+", ",", text)
    text = re.sub(r"\.\s*\.+", ".", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"-\s*-+", " ", text)
    text = text.strip(" ,-–—\t\r\n")

    if not text:
        return ""

    # Ensure proper sentence-ending punctuation
    if text[-1] not in ".!?।":
        if lang_code in ("hi", "bn", "mr", "ne"):
            text += "।"
        else:
            text += "."

    return text


def safe_translate(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate text with multi-engine fallback:
    GoogleTranslator → MyMemoryTranslator → original text (passthrough).
    """
    if not text:
        return ""

    src = source_lang.split("-")[0].lower() if source_lang else "en"
    tgt = target_lang.split("-")[0].lower() if target_lang else "en"

    if src == tgt:
        return text

    if GoogleTranslator is None:
        return text  # deep-translator not installed; graceful degradation

    # Engine 1: Google Translator
    try:
        result = GoogleTranslator(source=src, target=tgt).translate(text)
        if result:
            return result
    except Exception:
        pass

    # Engine 2: MyMemory Translator
    try:
        src_tag = f"{src}-IN" if len(src) == 2 else src
        tgt_tag = f"{tgt}-IN" if len(tgt) == 2 else tgt
        result = MyMemoryTranslator(source=src_tag, target=tgt_tag).translate(text)
        if result:
            return result
    except Exception:
        pass

    return text
