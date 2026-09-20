"""
Speech-output de-noising, unit normalization, and voice mapping.

Sourced and adapted from SOHAM-DEV2/WeatherGPT-MK1 (feature/voice-integrated-v1).
Keeps WeatherGPT's LLM output clean and natural for regional speech synthesis.
"""
import logging
import re
import warnings

logger = logging.getLogger(__name__)

# Translation engines (GoogleTranslator & MyMemoryTranslator fallback)
try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator
except ImportError:
    GoogleTranslator = None
    MyMemoryTranslator = None


# -----------------------------------------------------------------------
# Edge-TTS Neural Voice Map — All 22 Scheduled Indian Languages + English
# Strictly hardcoded: 'bn' -> bn-IN-TanishaaNeural, 'mr' -> mr-IN-AarohiNeural
# -----------------------------------------------------------------------

REGIONAL_VOICE_MAP: dict[str, str] = {
    "hi":  "hi-IN-SwaraNeural",               # Hindi
    "bn":  "bn-IN-TanishaaNeural",            # Bengali (STRICT: only Tanishaa)
    "mr":  "mr-IN-AarohiNeural",              # Marathi (STRICT: only Aarohi)
    "te":  "te-IN-ShrutiNeural",              # Telugu
    "ta":  "ta-IN-PallaviNeural",             # Tamil
    "gu":  "gu-IN-DhwaniNeural",              # Gujarati
    "ur":  "ur-IN-GulNeural",                 # Urdu
    "kn":  "kn-IN-SapnaNeural",               # Kannada
    "or":  "hi-IN-SwaraNeural",               # Odia (adaptive Indian neural)
    "ml":  "ml-IN-SobhanaNeural",             # Malayalam
    "pa":  "pa-IN-OjasNeural",                # Punjabi
    "as":  "bn-IN-TanishaaNeural",            # Assamese (Eastern Indic)
    "mai": "hi-IN-SwaraNeural",               # Maithili
    "sat": "hi-IN-SwaraNeural",               # Santali
    "ks":  "ur-IN-GulNeural",                 # Kashmiri
    "ne":  "ne-NP-HemkalaNeural",             # Nepali
    "kok": "mr-IN-AarohiNeural",              # Konkani (Marathi neural)
    "sd":  "ur-IN-GulNeural",                 # Sindhi
    "doi": "hi-IN-SwaraNeural",               # Dogri
    "mni": "bn-IN-TanishaaNeural",            # Manipuri
    "brx": "hi-IN-SwaraNeural",               # Bodo
    "sa":  "hi-IN-SwaraNeural",               # Sanskrit
    "en":  "en-IN-NeerjaExpressiveNeural",    # Indian English
}

PHONETIC_FALLBACK_MAP: dict[str, str] = {
    "mr":  "hi-IN-SwaraNeural",               # Marathi -> Hindi
    "kok": "mr-IN-AarohiNeural",              # Konkani -> Marathi
    "gu":  "hi-IN-SwaraNeural",               # Gujarati -> Hindi
    "pa":  "hi-IN-SwaraNeural",               # Punjabi -> Hindi
    "ne":  "hi-IN-SwaraNeural",               # Nepali -> Hindi
    "sa":  "hi-IN-SwaraNeural",               # Sanskrit -> Hindi
    "mai": "hi-IN-SwaraNeural",               # Maithili -> Hindi
    "doi": "hi-IN-SwaraNeural",               # Dogri -> Hindi
    "brx": "hi-IN-SwaraNeural",               # Bodo -> Hindi
    "sat": "hi-IN-SwaraNeural",               # Santali -> Hindi
    "as":  "bn-IN-TanishaaNeural",            # Assamese -> Bengali
    "mni": "bn-IN-TanishaaNeural",            # Manipuri -> Bengali
    "or":  "hi-IN-MadhurNeural",              # Odia -> Hindi Alternate (phonetic Devanagari)
    "bn":  "hi-IN-SwaraNeural",               # Bengali -> Hindi
    "ta":  "te-IN-ShrutiNeural",              # Tamil -> Telugu
    "te":  "ta-IN-PallaviNeural",             # Telugu -> Tamil
    "kn":  "te-IN-ShrutiNeural",              # Kannada -> Telugu
    "ml":  "ta-IN-PallaviNeural",             # Malayalam -> Tamil
    "ur":  "hi-IN-SwaraNeural",               # Urdu -> Hindi
    "ks":  "ur-IN-GulNeural",                 # Kashmiri -> Urdu
    "sd":  "ur-IN-GulNeural",                 # Sindhi -> Urdu
    "hi":  "hi-IN-MadhurNeural",              # Hindi -> Hindi Alternate
    "en":  "en-IN-PrabhatNeural",             # English -> English Alternate
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
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ڈگری سیلسیس",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 ڈگری فارن ہائیٹ",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 کلومیٹر فی گھنٹہ",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 میٹر فی سیکنڈ",
        r"(\d+(?:\.\d+)?)%":         r"\1 فیصد",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 ہیکٹو پاسکل",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 ملی میٹر",
    },
    "pa": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ਡਿਗਰੀ ਸੈਲਸੀਅਸ",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 ਡਿਗਰੀ ਫਾਰਨਹੀਟ",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 ਕਿਲੋਮੀਟਰ ਪ੍ਰਤੀ ਘੰਟਾ",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 ਮੀਟਰ ਪ੍ਰਤੀ ਸਕਿੰਟ",
        r"(\d+(?:\.\d+)?)%":         r"\1 ਪ੍ਰਤੀਸ਼ਤ",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 ਹੈਕਟੋਪਾਸਕਲ",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 ਮਿਲੀਮੀਟਰ",
    },
    "or": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ଡିଗ୍ରୀ ସେଲସିୟସ",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 ଡିଗ୍ରୀ ଫାରେନହାଇଟ",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 କିଲୋମିଟର ପ୍ରତି ଘଣ୍ଟା",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 ମିଟର ପ୍ରତି ସେକେଣ୍ଡ",
        r"(\d+(?:\.\d+)?)%":         r"\1 ପ୍ରତିଶତ",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 ହେକ୍ଟୋପାସ୍କାଲ",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 ମିଲିମିଟର",
    },
    "as": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 ডিগ্ৰী চেলচিয়াছ",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 ডিগ্ৰী ফাৰেনহাইট",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 কিলোমিটাৰ প্ৰতি ঘণ্টা",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 মিটাৰ প্ৰতি ছেকেণ্ড",
        r"(\d+(?:\.\d+)?)%":         r"\1 শতাংশ",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 হেক্টোপাস্কেল",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 মিলিমিটাৰ",
    },
    "ne": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 डिग्री सेल्सियस",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 डिग्री फरेनहाइट",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 किलोमिटर प्रति घण्टा",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 मिटर प्रति सेकेन्ड",
        r"(\d+(?:\.\d+)?)%":         r"\1 प्रतिशत",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 हेक्टोपास्कल",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 मिलिमिटर",
    },
    "sa": {
        r"(\d+(?:\.\d+)?)\s*°C":     r"\1 अंश सेल्शियस्",
        r"(\d+(?:\.\d+)?)\s*°F":     r"\1 अंश फारेनहायट्",
        r"(\d+(?:\.\d+)?)\s*km/h":   r"\1 किलोमीटर् प्रति घण्टा",
        r"(\d+(?:\.\d+)?)\s*m/s":    r"\1 मीटर् प्रति क्षणम्",
        r"(\d+(?:\.\d+)?)%":         r"\1 प्रतिशतम्",
        r"(\d+(?:\.\d+)?)\s*hPa":    r"\1 हेक्टोपास्कल्",
        r"(\d+(?:\.\d+)?)\s*mm":     r"\1 मिलिमीटर्",
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
def odia_to_phonetic_devanagari(text: str) -> str:
    """
    Transliterates Odia script (U+0B00–U+0B7F) to phonetic Devanagari script (U+0900–U+097F).
    Both scripts share an exact 1-to-1 Brahmi Unicode layout with an offset of 0x0200.
    Enables Edge-TTS Hindi neural voice (hi-IN-SwaraNeural) to synthesize native Odia words
    flawlessly without crashing or remaining silent.
    """
    if not text:
        return ""
    result = []
    for ch in text:
        code = ord(ch)
        if 0x0B00 <= code <= 0x0B7F:
            if code == 0x0B5F:    # Odia YAA ୟ
                result.append("\u092F")
            elif code == 0x0B71:  # Odia WA ୱ
                result.append("\u0935")
            elif code == 0x0B5C:  # Odia RRA ଡ଼
                result.append("\u095C")
            elif code == 0x0B5D:  # Odia RHA ଢ଼
                result.append("\u095D")
            else:
                deva_code = code - 0x0200
                if 0x0900 <= deva_code <= 0x097F:
                    result.append(chr(deva_code))
                else:
                    result.append(ch)
        else:
            result.append(ch)
    return "".join(result)


# Map regional languages without separate number tables to their linguistic parent
LANG_NUMBER_MAP_ALIASES: dict[str, str] = {
    "kok": "mr",   # Konkani -> Marathi numerals & unit terms
    "mai": "hi",   # Maithili -> Hindi numerals & unit terms
    "doi": "hi",   # Dogri -> Hindi numerals & unit terms
    "brx": "hi",   # Bodo -> Devanagari numerals & unit terms
    "ks":  "ur",   # Kashmiri -> Perso-Arabic numerals & unit terms
    "sd":  "ur",   # Sindhi -> Perso-Arabic numerals & unit terms
    "mni": "bn",   # Manipuri -> Bengali numerals & unit terms
    "sat": "hi",   # Santali -> Devanagari numerals & unit terms
}


# -----------------------------------------------------------------------
class VoiceCleaner:
    """Pre-Synthesis Script Guardian and Linguistic Lock Validator."""

    EASTERN_NAGARI_REGEX = re.compile(r"[\u0980-\u09FF]")  # Bengali / Assamese / Manipuri
    DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")      # Hindi / Marathi / Sanskrit / Nepali / Konkani / Maithili / Bodo / Dogri
    PERSO_ARABIC_REGEX = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")  # Urdu / Kashmiri / Sindhi
    ODIA_REGEX = re.compile(r"[\u0B00-\u0B7F]")            # Odia script

    @classmethod
    def detect_script(cls, text: str) -> str:
        """Return 'bn' for Bengali, 'devanagari' for Devanagari, 'ur' for Perso-Arabic, 'or' for Odia, or 'other'."""
        if not text:
            return "other"
        if cls.PERSO_ARABIC_REGEX.search(text):
            return "ur"
        if cls.ODIA_REGEX.search(text):
            return "or"
        bn_count = len(cls.EASTERN_NAGARI_REGEX.findall(text))
        deva_count = len(cls.DEVANAGARI_REGEX.findall(text))
        if bn_count > 0 and bn_count >= deva_count:
            return "bn"
        if deva_count > 0:
            return "devanagari"
        return "other"

    @classmethod
    def sanitize_voice_for_script(
        cls,
        voice_name: str,
        text: str,
        target_lang: str | None = None,
    ) -> tuple[str, str]:
        """
        Guarantees that each of the 22 Indian languages is synthesized via the correct
        neural engine without audio dropping or script mismatch failures.
        """
        norm_target = (target_lang or "").strip().lower().split("-")[0]
        detected = cls.detect_script(text)

        # 1. Perso-Arabic family (Urdu, Kashmiri, Sindhi)
        if norm_target in ("ur", "ks", "sd") or detected == "ur":
            chosen_lang = norm_target if norm_target in ("ur", "ks", "sd") else "ur"
            return "ur-IN-GulNeural", chosen_lang

        # 2. Odia: spoken via adaptive Indian neural with phonetic Devanagari
        if norm_target == "or" or detected == "or":
            return "hi-IN-SwaraNeural", "or"

        # 3. Eastern Nagari family (Bengali, Assamese, Manipuri)
        if norm_target in ("bn", "as", "mni") or detected == "bn":
            chosen_lang = norm_target if norm_target in ("bn", "as", "mni") else "bn"
            return "bn-IN-TanishaaNeural", chosen_lang

        # 4. Marathi & Konkani
        if norm_target in ("mr", "kok"):
            return "mr-IN-AarohiNeural", norm_target

        # 5. Hindi & Devanagari regional languages (Maithili, Dogri, Bodo, Sanskrit, Santali)
        if norm_target in ("hi", "mai", "doi", "brx", "sa", "sat"):
            return "hi-IN-SwaraNeural", norm_target

        # 6. Fall back to standard registry
        if norm_target in REGIONAL_VOICE_MAP:
            return REGIONAL_VOICE_MAP[norm_target], norm_target

        return voice_name, norm_target or "en"


def get_voice_for_language(lang_code: str) -> str:
    """Return the optimal Edge-TTS Neural Voice for the given ISO language code.
    Strictly follows target_lang. Prohibits 'auto' guessing."""
    if not lang_code:
        return REGIONAL_VOICE_MAP["en"]
    norm = lang_code.strip().lower()
    if norm in ("auto", "none", ""):
        raise ValueError("Linguistic Lock: Explicit target_lang required for voice synthesis, 'auto' is prohibited.")
    if norm in REGIONAL_VOICE_MAP:
        return REGIONAL_VOICE_MAP[norm]
    short = norm.split("-")[0].split("_")[0]
    if short in REGIONAL_VOICE_MAP:
        return REGIONAL_VOICE_MAP[short]
    return REGIONAL_VOICE_MAP.get("hi", "hi-IN-SwaraNeural")



def get_phonetic_fallback_voice(lang_code: str) -> str:
    """Return the closest phonetic fallback neural voice if the primary voice fails.
    Guarantees that regional Indian languages never crash or inappropriately fall back to English."""
    if not lang_code:
        return "hi-IN-SwaraNeural"
    norm = lang_code.strip().lower().split("-")[0].split("_")[0]
    return PHONETIC_FALLBACK_MAP.get(norm, "hi-IN-SwaraNeural")


# -----------------------------------------------------------------------
# Input De-Noising Pre-processor (Task 4)
# Strips filler words and non-lexical sounds (uh, ah, breathing, coughing, etc.)
# -----------------------------------------------------------------------
NON_LEXICAL_SOUNDS_PATTERN = re.compile(
    r"\[(?:breathing|sigh|gasp|cough|throat-clearing|clears throat|laughter|applause|music|groan|snort|snicker|sound|noise|whispering|silence)\]"
    r"|\((?:breathing|sigh|gasp|cough|throat-clearing|clears throat|laughter|applause|music|groan|snort|snicker|sound|noise|whispering|silence)\)"
    r"|\*(?:breathing|sigh|gasp|cough|throat-clearing|clears throat|laughter|music|groan)\*",
    flags=re.IGNORECASE,
)

FILLER_WORDS_PATTERN = re.compile(
    r"\b(?:uh|um|er|erm|ah|ahh|umm|uhh|hmm|mhm|huh|ha|phew)\b",
    flags=re.IGNORECASE,
)

INDIC_FILLER_WORDS_PATTERN = re.compile(
    r"(?:^|\s)(?:अह|उह|उम|अम्म|हम्म|हँ|आह|अं|हं|আহ|উম|হুম|উহ|অহ)(?:\s|$|[,\.!?])",
    flags=re.IGNORECASE,
)


def clean_transcribed_input(text: str) -> str:
    """Pre-processor that removes filler words, hesitation sounds, breathing,
    and non-lexical acoustic noise before passing text to the translation and RAG layers.
    """
    if not text:
        return ""

    cleaned = text.strip()

    # 1. Remove non-lexical sound brackets e.g. [breathing], (sigh), [cough]
    cleaned = NON_LEXICAL_SOUNDS_PATTERN.sub(" ", cleaned)

    # 2. Remove English/Latin filler words e.g. uh, um, ah, er, hmm
    cleaned = FILLER_WORDS_PATTERN.sub(" ", cleaned)

    # 3. Remove Indic/Devanagari/Bengali non-lexical hesitation tokens
    cleaned = INDIC_FILLER_WORDS_PATTERN.sub(" ", cleaned)

    # 4. Clean stray punctuation left after removing fillers
    cleaned = re.sub(r"\s*([,;:\.!?])\s*", r"\1 ", cleaned)
    cleaned = re.sub(r"^[,;:\s\-]+", "", cleaned)
    cleaned = re.sub(r"[,;\s\-]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned



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


# -----------------------------------------------------------------------
# Multi-Lingual Spoken Number Dictionaries (0 to 100 & Decimals)
# Eliminates Edge-TTS American/English Accent Drift on Numbers & Metrics
# -----------------------------------------------------------------------
DECIMAL_WORD_MAP: dict[str, str] = {
    "hi": "दशमलव",
    "mr": "दशमलव",
    "ne": "दशमलव",
    "sa": "दशमलव",
    "bn": "দশমিক",
    "as": "দশমিক",
    "pa": "ਦਸ਼ਮਲਵ",
    "gu": "દશાંશ",
    "or": "ଦଶମିକ",
    "ta": "புள்ளி",
    "te": "పాయింట్",
    "kn": "ಬಿಂದು",
    "ml": "പോയിന്റ്",
    "ur": "اعشاریہ",
    "en": "point",
}

DIGIT_WORD_MAP: dict[str, list[str]] = {
    "hi": ["शून्य", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ"],
    "bn": ["শূন্য", "এক", "দুই", "তিন", "চার", "পাঁচ", "ছয়", "সাত", "আট", "নয়"],
    "ta": ["பூஜ்யம்", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு", "ஐந்து", "ஆறு", "ஏழு", "எட்டு", "ஒன்பது"],
    "te": ["సున్నా", "ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "ఆరు", "ఏడు", "ఎనిమిది", "తొమ్మిది"],
    "mr": ["शून्य", "एक", "दोन", "तीन", "चार", "पाच", "सहा", "सात", "आठ", "नऊ"],
    "gu": ["શૂન્ય", "એક", "બે", "ત્રણ", "ચાર", "પાંચ", "છ", "સાત", "આઠ", "નવ"],
    "kn": ["ಸೊನ್ನೆ", "ಒಂದು", "ಎರಡು", "ಮೂರು", "ನಾಲ್ಕು", "ಐದು", "ಆರು", "ಏಳು", "ಎಂಟು", "ಒಂಬತ್ತು"],
    "ml": ["പൂജ്യം", "ഒന്ന്", "രണ്ട്", "മൂന്ന്", "നാല്", "അഞ്ച്", "ആറ്", "ഏഴ്", "എട്ട്", "ഒമ്പത്"],
    "ur": ["صفر", "ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو"],
    "pa": ["ਸਿਫ਼ਰ", "ਇੱਕ", "ਦੋ", "ਤਿੰਨ", "ਚਾਰ", "ਪੰਜ", "ਛੇ", "ਸੱਤ", "ਅੱਠ", "ਨੌਂ"],
    "or": ["ଶୂନ", "ଏକ", "ଦୁଇ", "ତିନି", "ଚାରି", "ପାଞ୍ଚ", "ଛଅ", "ସାତ", "ଆଠ", "ନଅ"],
    "as": ["শূন্য", "এক", "দুই", "তিনি", "চাৰি", "পাঁচ", "ছয়", "সাত", "আঠ", "ন"],
    "ne": ["शून्य", "एक", "दुई", "तीन", "चार", "पाँच", "छ", "सात", "आठ", "नौ"],
    "sa": ["शून्यम्", "एकम्", "द्वे", "त्रीणि", "चत्वारि", "पञ्च", "षट्", "सप्त", "अष्ट", "नव"],
    "en": ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"],
}

INTEGER_WORD_MAP: dict[str, dict[int, str]] = {
    "hi": {
        0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच", 6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
        11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह", 16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस",
        20: "बीस", 21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस", 26: "छब्बीस", 27: "सत्ताईस", 28: "अट्ठाईस", 29: "उनतीस",
        30: "तीस", 31: "इकत्तीस", 32: "बत्तीस", 33: "तैंतीस", 34: "चौंतीस", 35: "पैंतीस", 36: "छत्तीस", 37: "सैंतीस", 38: "अड़तीस", 39: "उनतालीस",
        40: "चालीस", 41: "इकतालीस", 42: "बयालीस", 43: "तैंतालीस", 44: "चवालीस", 45: "पैंतालीस", 46: "छियालीस", 47: "सैंतालीस", 48: "अड़तालीस", 49: "उनचास",
        50: "पचास", 51: "इक्यावन", 52: "बावन", 53: "तिरपन", 54: "चौवन", 55: "पचपन", 56: "छप्पन", 57: "सत्तावन", 58: "अट्ठावन", 59: "उनसठ",
        60: "साठ", 70: "सत्तर", 80: "अस्सी", 90: "नब्बे", 100: "सौ",
    },
    "bn": {
        0: "শূন্য", 1: "এক", 2: "দুই", 3: "তিন", 4: "চার", 5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আট", 9: "নয়", 10: "দশ",
        11: "এগারো", 12: "বারো", 13: "তেরো", 14: "চৌদ্দ", 15: "পনেরো", 16: "ষোল", 17: "সতেরো", 18: "আঠারো", 19: "উনিশ",
        20: "বিশ", 21: "একুশ", 22: "বাইশ", 23: "তেইশ", 24: "চব্বিশ", 25: "পঁচিশ", 26: "ছাব্বিশ", 27: "সাতাশ", 28: "আঠাশ", 29: "উনত্রিশ",
        30: "ত্রিশ", 31: "একত্রিশ", 32: "বত্রিশ", 33: "তেত্রিশ", 34: "চৌত্রিশ", 35: "পঁয়ত্রিশ", 40: "চল্লিশ", 45: "পঁয়তাল্লিশ",
        50: "পঞ্চাশ", 60: "ষাট", 70: "সत्तर", 80: "আশি", 90: "নব্বই", 100: "একশত",
    },
    "ta": {
        0: "பூஜ்யம்", 1: "ஒன்று", 2: "இரண்டு", 3: "மூன்று", 4: "நான்கு", 5: "ஐந்து", 6: "ஆறு", 7: "ஏழு", 8: "எட்டு", 9: "ஒன்பது", 10: "பத்து",
        11: "பதினொன்று", 12: "பன்னிரண்டு", 13: "பதின்மூன்று", 14: "பதினான்கு", 15: "பதினைந்து", 16: "பதினாறு", 17: "பதினேழு", 18: "பதினெட்டு", 19: "பத்தொன்பது",
        20: "இருபது", 21: "இருபத்து ஒன்று", 22: "இருபத்து இரண்டு", 23: "இருபத்து மூன்று", 24: "இருபத்து நான்கு", 25: "இருபத்து ஐந்து",
        26: "இருபத்து ஆறு", 27: "இருபத்து ஏழு", 28: "இருபத்து எட்டு", 29: "இருபத்து ஒன்பது", 30: "முப்பது", 31: "முப்பத்து ஒன்று",
        32: "முப்பத்து இரண்டு", 35: "முப்பத்து ஐந்து", 40: "நாற்பது", 45: "நாற்பத்து ஐந்து", 50: "ஐம்பது", 60: "அறுபது", 70: "எழுபது", 80: "எண்பது", 90: "தொண்ணூறு", 100: "நூறு",
    },
    "te": {
        0: "సున్నా", 1: "ఒకటి", 2: "రెండు", 3: "మూడు", 4: "నాలుగు", 5: "ఐదు", 6: "ఆరు", 7: "ఏడు", 8: "ఎనిమిది", 9: "తొమ్మిది", 10: "పది",
        11: "పదకొండు", 12: "పన్నెండు", 13: "పదమూడు", 14: "పద్నాలుగు", 15: "పదిహేను", 16: "పదహారు", 17: "పదిహేడు", 18: "పద్దెనిమిది", 19: "పంతొమ్మిది",
        20: "ఇరవై", 21: "ఇరవై ఒకటి", 22: "ఇరవై రెండు", 23: "ఇరవై మూడు", 24: "ఇరవై నాలుగు", 25: "ఇరవై ఐదు",
        28: "ఇరవై ఎనిమిది", 29: "ఇరవై తొమ్మిది", 30: "ముప్పై", 31: "ముప్పై ఒకటి", 32: "ముప్పై రెండు", 35: "ముప్పై ఐదు",
        40: "నలభై", 45: "నలభై ఐదు", 50: "యాభై", 60: "అరవై", 70: "డెబ్బై", 80: "ఎనభై", 90: "తొంభై", 100: "వంద",
    },
    "ur": {
        0: "صفر", 1: "ایک", 2: "دو", 3: "تین", 4: "چار", 5: "پانچ", 6: "چھ", 7: "سات", 8: "آٹھ", 9: "نو", 10: "دس",
        11: "گیارہ", 12: "بارہ", 13: "تیرہ", 14: "چودہ", 15: "پندرہ", 16: "سولہ", 17: "سترہ", 18: "اٹھارہ", 19: "انیس",
        20: "بیس", 21: "اکیس", 22: "بائیس", 23: "تیئیس", 24: "چوبیس", 25: "پچیس", 26: "چھبیس", 27: "ستائیس", 28: "اٹھائیس", 29: "انتیس",
        30: "تیس", 31: "اکتیس", 32: "بتیس", 35: "پینتیس", 40: "چالیس", 45: "پینتالیس", 50: "پچاس", 55: "پچپن", 60: "ساٹھ", 65: "پینسٹھ", 70: "ستر", 75: "پچہتر", 80: "اسی", 85: "پچاسی", 90: "نوے", 95: "پچانوے", 100: "سو",
    },
    "pa": {
        0: "ਸਿਫ਼ਰ", 1: "ਇੱਕ", 2: "ਦੋ", 3: "ਤਿੰਨ", 4: "ਚਾਰ", 5: "ਪੰਜ", 6: "ਛੇ", 7: "ਸੱਤ", 8: "ਅੱਠ", 9: "ਨੌਂ", 10: "ਦਸ",
        11: "ਗਿਆਰਾਂ", 12: "ਬਾਰਾਂ", 13: "ਤੇਰਾਂ", 14: "ਚੌਦਾਂ", 15: "ਪੰਦਰਾਂ", 16: "ਸੋਲਾਂ", 17: "ਸਤਾਰਾਂ", 18: "ਅਠਾਰਾਂ", 19: "ਉੱਨੀ",
        20: "ਵੀਹ", 21: "ਇੱਕੀ", 22: "ਬਾਈ", 23: "ਤੇਈ", 24: "ਚੌਵੀ", 25: "ਪੱਚੀ", 28: "ਅਠਾਈ", 29: "ਉਣੱਤੀ",
        30: "ਤੀਹ", 31: "ਇਕੱਤੀ", 32: "ਬੱਤੀ", 35: "ਪੈਂਤੀ", 40: "ਚਾਲੀ", 45: "ਪੰਤਾਲੀ", 50: "ਪੰਜਾਹ", 60: "ਸੱਠ", 70: "ਸੱਤਰ", 80: "ਅੱਸੀ", 90: "ਨੱਬੇ", 100: "ਸੌ",
    },
    "mr": {
        0: "शून्य", 1: "एक", 2: "दोन", 3: "तीन", 4: "चार", 5: "पाच", 6: "सहा", 7: "सात", 8: "आठ", 9: "नऊ", 10: "दहा",
        11: "अकरा", 12: "बारा", 13: "तेरा", 14: "चौदा", 15: "पंधरा", 16: "सोळा", 17: "सतरा", 18: "अठरा", 19: "एकोणीस",
        20: "वीस", 21: "एकवीस", 22: "बावीस", 23: "तेवीस", 24: "चोवीस", 25: "पंचवीस", 28: "अठ्ठावीस", 29: "एकोणतीस",
        30: "तीस", 31: "एकतीस", 32: "बत्तीस", 35: "पस्तीस", 40: "चाळीस", 45: "पंचेचाळीस", 50: "पन्नास", 60: "साठ", 70: "सत्तर", 80: "ऐंशी", 90: "नव्वद", 100: "शंभर",
    },
    "gu": {
        0: "શૂન્ય", 1: "એક", 2: "બે", 3: "ત્રણ", 4: "ચાર", 5: "પાંચ", 6: "છ", 7: "સાત", 8: "આઠ", 9: "નવ", 10: "દસ",
        11: "અગિયાર", 12: "બાર", 13: "તેર", 14: "ચૌદ", 15: "પંદર", 16: "સોળ", 17: "સત્તર", 18: "અઢાર", 19: "ઓગણિસ",
        20: "વીસ", 21: "એકવીસ", 22: "બાવીસ", 23: "તેવીસ", 24: "ચોવીસ", 25: "પચ્ચીસ", 28: "અઠ્ઠાવીસ", 29: "ઓગણત્રીસ",
        30: "ત્રીસ", 31: "એકત્રીસ", 32: "બત્રીસ", 35: "પાંત્રીસ", 40: "ચાલીસ", 45: "પિસ્તાલીસ", 50: "પચાસ", 60: "સાઠ", 70: "સિત્તેર", 80: "એંસી", 90: "નેવું", 100: "સો",
    },
    "kn": {
        0: "ಸೊನ್ನೆ", 1: "ಒಂದು", 2: "ಎರಡು", 3: "ಮೂರು", 4: "ನಾಲ್ಕು", 5: "ಐದು", 6: "ಆರು", 7: "ಏಳು", 8: "ಎಂಟು", 9: "ಒಂಬತ್ತು", 10: "ಹತ್ತು",
        11: "ಹನ್ನೊಂದು", 12: "ಹನ್ನೆರಡು", 13: "ಹದಿಮೂರು", 14: "ಹದಿನಾಲ್ಕು", 15: "ಹದಿನೈದು", 16: "ಹದಿನಾರು", 17: "ಹದಿನೇಳು", 18: "ಹದಿನೆಂಟು", 19: "ಹತ್ತೊಂಬತ್ತು",
        20: "ಇಪ್ಪತ್ತು", 21: "ಇಪ್ಪತ್ತೊಂದು", 22: "ಇಪ್ಪತ್ತೆರಡು", 23: "ಇಪ್ಪತ್ತಮೂರು", 24: "ಇಪ್ಪತ್ತನಾಲ್ಕು", 25: "ಇಪ್ಪತ್ತೈದು",
        28: "ಇಪ್ಪತ್ತೆಂಟು", 29: "ಇಪ್ಪತ್ತೊಂಬತ್ತು", 30: "ಮೂವತ್ತು", 31: "ಮೂವತ್ತೊಂದು", 32: "ಮೂವತ್ತೆರಡು", 35: "ಮೂವತ್ತೈದು",
        40: "ನಲವತ್ತು", 45: "ನಲವತ್ತೈದು", 50: "ಐವತ್ತು", 60: "ಅರವತ್ತು", 70: "ಎಪ್ಪತ್ತು", 80: "ಎಂಬತ್ತು", 90: "ತೊಂಬತ್ತು", 100: "ನೂರು",
    },
    "ml": {
        0: "പൂജ്യം", 1: "ഒന്ന്", 2: "രണ്ട്", 3: "മൂന്ന്", 4: "നാല്", 5: "അഞ്ച്", 6: "ആറ്", 7: "ഏഴ്", 8: "എട്ട്", 9: "ഒമ്പത്", 10: "പത്ത്",
        11: "പതിനൊന്ന്", 12: "പന്ത്രണ്ട്", 13: "പതിമൂന്ന്", 14: "പതിനാല്", 15: "പതിനഞ്ച്", 16: "പതിനാറ്", 17: "പതിനേഴ്", 18: "പതിനെട്ട്", 19: "പത്തൊമ്പത്",
        20: "ഇരുപത്", 21: "ഇരുപത്തൊന്ന്", 22: "ഇരുപത്തിരണ്ട്", 23: "ഇരുപത്തിമൂന്ന്", 24: "ഇരുപത്തിനാല്", 25: "ഇരുപത്തിയഞ്ച്",
        28: "ഇരുപത്തിയെട്ട്", 29: "ഇരുപത്തിയൊമ്പത്", 30: "മുപ്പത്", 31: "മുപ്പത്തൊന്ന്", 32: "മുപ്പത്തിരണ്ട്", 35: "മുപ്പത്തിയഞ്ച്",
        40: "നാൽപ്പത്", 45: "നാൽപ്പത്തിയഞ്ച്", 50: "അൻപത്", 60: "അറുപത്", 70: "എഴുപത്", 80: "എൺപത്", 90: "തൊണ്ണൂറ്", 100: "നൂറ്",
    },
    "or": {
        0: "ଶୂନ", 1: "ଏକ", 2: "ଦୁଇ", 3: "ତିନି", 4: "ଚାରି", 5: "ପାଞ୍ଚ", 6: "ଛଅ", 7: "ସାତ", 8: "ଆଠ", 9: "ନଅ", 10: "ଦଶ",
        11: "ଏଗାର", 12: "ବାର", 13: "ତେର", 14: "ଚଉଦ", 15: "ପନ୍ଦର", 16: "ଷୋହଳ", 17: "ସତର", 18: "ଅଠର", 19: "ଉଣାଇଶ",
        20: "କୋଡ଼ିଏ", 21: "ଏକୋଇଶ", 22: "ବାଇଶ", 23: "ତେଇଶ", 24: "ଚବିଶ", 25: "ପଚିଶ", 28: "ଅଠେଇଶ", 29: "ଅଣତିରିଶ",
        30: "ତିରିଶ", 31: "ଏକତିରିଶ", 32: "ବତିଶ", 35: "ପଞ୍ଚତିରିଶ", 40: "ଚାଳିଶ", 45: "ପଞ୍ଚଚାଳିଶ", 50: "ପଚାଶ", 60: "ଷାଠିଏ", 70: "ସତୁରି", 80: "ଅଶୀ", 90: "ନବ୍ବେ", 100: "ଏକ ଶହ",
    },
    "as": {
        0: "শূন্য", 1: "এক", 2: "দুই", 3: "তিনি", 4: "চাৰি", 5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আঠ", 9: "ন", 10: "দহ",
        11: "এঘাৰ", 12: "বাৰ", 13: "তেৰ", 14: "চৈধ্য", 15: "পোন্ধৰ", 16: "ষোল্ল", 17: "সোতৰ", 18: " ওঠৰ", 19: "ঊনৈশ",
        20: "বিশ", 21: "একৈশ", 22: "বাইশ", 23: "তেইশ", 24: "চৌব্বিশ", 25: "পঁচিশ", 28: "আঠাইশ", 29: "উনত্ৰিশ",
        30: "ত্ৰিশ", 31: "একত্ৰিশ", 32: "বত্ৰিশ", 35: "পঁয়ত্ৰিশ", 40: "চল্লিছ", 45: "পয়তালিছ", 50: "পঞ্চাশ", 60: "ষাঠি", 70: "সত্তৰ", 80: "আশী", 90: "নব্বৈ", 100: "এশ",
    },
    "ne": {
        0: "शून्य", 1: "एक", 2: "दुई", 3: "तीन", 4: "चार", 5: "पाँच", 6: "छ", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
        11: "एघार", 12: "बाह्र", 13: "तेह्र", 14: "चौध", 15: "पन्ध्र", 16: "सोह्र", 17: "सत्र", 18: "अठार", 19: "उन्नाइस",
        20: "बीस", 21: "एक्काइस", 22: "बाइस", 23: "तेइस", 24: "चौबीस", 25: "पच्चीस", 28: "अट्ठाइस", 29: "उनन्तीस",
        30: "तीस", 31: "एकत्तीस", 32: "बत्तीस", 35: "पैंतीस", 40: "चालीस", 45: "पैंतालीस", 50: "पचास", 60: "साठ", 70: "सत्तर", 80: "अस्सी", 90: "नब्बे", 100: "सय",
    },
    "sa": {
        0: "शून्यम्", 1: "एकम्", 2: "द्वे", 3: "त्रीणि", 4: "चत्वारि", 5: "पञ्च", 6: "षट्", 7: "सप्त", 8: "अष्ट", 9: "नव", 10: "दश",
        11: "एकादश", 12: "द्वादश", 13: "त्रयोदश", 14: "चतुर्दश", 15: "पञ्चदश", 16: "षोडश", 17: "सप्तदश", 18: "अष्टादश", 19: "नवदश",
        20: "विंशतिः", 21: "एकविंशतिः", 22: "द्वाविंशतिः", 28: "अष्टाविंशतिः", 29: "एकोनत्रिंशत्",
        30: "त्रिंशत्", 31: "एकत्रिंशत्", 32: "द्वौत्रिंशत्", 35: "पञ्चत्रिंशत्", 40: "चत्वारिंशत्", 45: "पञ्चचत्वारिंशत्",
        50: "पञ्चाशत्", 60: "षष्टिः", 70: "सप्ततिः", 80: "अशीतिः", 90: "नवतिः", 100: "शतम्",
    },
    "en": {
        0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
        11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
        20: "twenty", 21: "twenty-one", 22: "twenty-two", 23: "twenty-three", 24: "twenty-four", 25: "twenty-five",
        28: "twenty-eight", 29: "twenty-nine", 30: "thirty", 31: "thirty-one", 32: "thirty-two", 35: "thirty-five",
        40: "forty", 45: "forty-five", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety", 100: "one hundred",
    },
}

NATIVE_UNIT_LABELS: dict[str, dict[str, str]] = {
    "hi": {
        "celsius": "डिग्री सेल्सियस", "fahrenheit": "डिग्री फारेनहाइट",
        "kmh": "किलोमीटर प्रति घंटा", "ms": "मीटर प्रति सेकंड",
        "percent": "प्रतिशत", "hpa": "हेक्टोपास्कल", "mm": "मिलीमीटर",
    },
    "bn": {
        "celsius": "ডিগ্রি সেলসিয়াস", "fahrenheit": "ডিগ্রি ফারেনহাইট",
        "kmh": "কিলোমিটার প্রতি ঘণ্টা", "ms": "মিটার প্রতি সেকেন্ড",
        "percent": "শতাংশ", "hpa": "হেক্টোপাস্কাল", "mm": "মিলিমিটার",
    },
    "ta": {
        "celsius": "டிகிரி செல்சியஸ்", "fahrenheit": "டிகிரி பாரன்ஹீட்",
        "kmh": "கிலோமீட்டர் மணி வேகம்", "ms": "மீட்டர் வினாடிக்கு",
        "percent": "சதவீதம்", "hpa": "ஹெக்டோபாஸ்கல்", "mm": "மில்லிமீட்டர்",
    },
    "te": {
        "celsius": "డిగ్రీల సెల్సియస్", "fahrenheit": "డిగ్రీల ఫారెన్‌హీట్",
        "kmh": "కిలోమీటర్లు గంటకు", "ms": "మీటర్లు సెకనుకు",
        "percent": "శాతం", "hpa": "హెక్టోపాస్కల్", "mm": "మిల్లీమీటర్లు",
    },
    "ur": {
        "celsius": "ڈگری سیلسیس", "fahrenheit": "ڈگری فارن ہائیٹ",
        "kmh": "کلومیٹر فی گھنٹہ", "ms": "میٹر فی سیکنڈ",
        "percent": "فیصد", "hpa": "ہیکٹو پاسکل", "mm": "ملی میٹر",
    },
    "pa": {
        "celsius": "ਡਿਗਰੀ ਸੈਲਸੀਅਸ", "fahrenheit": "ਡਿਗਰੀ ਫਾਰਨਹੀਟ",
        "kmh": "ਕਿਲੋਮੀਟਰ ਪ੍ਰਤੀ ਘੰਟਾ", "ms": "ਮੀਟਰ ਪ੍ਰਤੀ ਸਕਿੰਟ",
        "percent": "ਪ੍ਰਤੀਸ਼ਤ", "hpa": "ਹੈਕਟੋਪਾਸਕਲ", "mm": "ਮਿਲੀਮੀਟਰ",
    },
    "mr": {
        "celsius": "अंश सेल्सिअस", "fahrenheit": "अंश फारेनहाइट",
        "kmh": "किलोमीटर प्रति तास", "ms": "मीटर प्रति सेकंद",
        "percent": "टक्के", "hpa": "हेक्टोपास्कल", "mm": "मिलिमीटर",
    },
    "gu": {
        "celsius": "ડિગ્રી સેલ્સિયસ", "fahrenheit": "ડિગ્રી ફેરનહીટ",
        "kmh": "કિલોમીટર પ્રતિ કલાક", "ms": "મીટર પ્રતિ સેકન્ડ",
        "percent": "ટકા", "hpa": "હેક્ટોપાસ્કલ", "mm": "મિલીમીટર",
    },
    "kn": {
        "celsius": "ಡಿಗ್ರಿ ಸೆಲ್ಸಿಯಸ್", "fahrenheit": "ಡಿಗ್ರಿ ಫ್ಯಾರನ್‌ಹೀಟ್",
        "kmh": "ಕಿಲೋಮೀಟರ್ ಪ್ರತಿ ಗಂಟೆ", "ms": "ಮೀಟರ್ ಪ್ರತಿ ಸೆಕೆಂಡ್",
        "percent": "ಪ್ರತಿಶತ", "hpa": "ಹೆಕ್ಟೋಪಾಸ್ಕಲ್", "mm": "ಮಿಲಿಮೀಟರ್",
    },
    "ml": {
        "celsius": "ഡിഗ്രി സെൽഷ്യസ്", "fahrenheit": "ഡിഗ്രി ഫാരൻഹീറ്റ്",
        "kmh": "കിലോമീറ്റർ പ്രതി മണിക്കൂർ", "ms": "മീറ്റർ പ്രതി സെക്കൻഡ്",
        "percent": "ശതമാനം", "hpa": "ഹെക്ടോപാസ്കൽ", "mm": "മില്ലിമീറ്റർ",
    },
    "or": {
        "celsius": "ଡିଗ୍ରୀ ସେଲସିୟସ", "fahrenheit": "ଡିଗ୍ରୀ ଫାରେନହାଇଟ",
        "kmh": "କିଲୋମିଟର ପ୍ରତି ଘଣ୍ଟା", "ms": "ମିଟର ପ୍ରତି ସେକେଣ୍ଡ",
        "percent": "ପ୍ରତିଶତ", "hpa": "ହେକ୍ଟୋପାସ୍କାଲ", "mm": "ମିଲିମିଟର",
    },
    "as": {
        "celsius": "ডিগ্ৰী চেলচিয়াছ", "fahrenheit": "ডিগ্ৰী ফাৰেনহাইট",
        "kmh": "কিলোমিটাৰ প্ৰতি ঘণ্টা", "ms": "মিটাৰ প্ৰতি ছেকেণ্ড",
        "percent": "শতাংশ", "hpa": "হেক্টোপাস্কেল", "mm": "মিলিমিটাৰ",
    },
    "ne": {
        "celsius": "डिग्री सेल्सियस", "fahrenheit": "डिग्री फरेनहाइट",
        "kmh": "किलोमिटर प्रति घण्टा", "ms": "मिटर प्रति सेकेन्ड",
        "percent": "प्रतिशत", "hpa": "हेक्टोपास्कल", "mm": "मिलिमिटर",
    },
    "sa": {
        "celsius": "अंश सेल्शियस्", "fahrenheit": "अंश फारेनहायट्",
        "kmh": "किलोमीटर् प्रति घण्टा", "ms": "मीटर् प्रति क्षणम्",
        "percent": "प्रतिशतम्", "hpa": "हेक्टोपास्कल्", "mm": "मिलिमीटर्",
    },
    "en": {
        "celsius": "degrees Celsius", "fahrenheit": "degrees Fahrenheit",
        "kmh": "kilometers per hour", "ms": "meters per second",
        "percent": "percent", "hpa": "hectopascals", "mm": "millimeters",
    },
}


def convert_integer_to_words(int_str: str, lang_code: str) -> str:
    """Convert integer string to native language word."""
    try:
        val = int(int_str)
    except ValueError:
        return int_str

    num_dict = INTEGER_WORD_MAP.get(lang_code, INTEGER_WORD_MAP["en"])
    if val in num_dict:
        return num_dict[val]

    # For larger numbers or unmapped values: speak digit by digit
    digits_table = DIGIT_WORD_MAP.get(lang_code, DIGIT_WORD_MAP["en"])
    return " ".join(digits_table[int(d)] if d.isdigit() else d for d in int_str)


def convert_number_to_words(num_str: str, lang_code: str = "en") -> str:
    """Convert an integer or decimal number string into native words for lang_code."""
    short_lang = lang_code.split("-")[0].lower() if lang_code else "en"
    if short_lang not in INTEGER_WORD_MAP:
        short_lang = LANG_NUMBER_MAP_ALIASES.get(short_lang, "en")

    # Handle decimals (e.g. 29.4)
    if "." in num_str:
        parts = num_str.split(".", 1)
        int_part_str, dec_part_str = parts[0], parts[1]
        int_word = convert_integer_to_words(int_part_str, short_lang)
        dec_label = DECIMAL_WORD_MAP.get(short_lang, "point")
        digits_table = DIGIT_WORD_MAP.get(short_lang, DIGIT_WORD_MAP["en"])
        dec_words = " ".join(digits_table[int(d)] if d.isdigit() else d for d in dec_part_str)
        return f"{int_word} {dec_label} {dec_words}".strip()

    return convert_integer_to_words(num_str, short_lang)


def prepare_for_tts(text: str, lang: str = "en") -> str:
    """
    Task 4: Unit & Number Normalization for Edge-TTS across all 22 scheduled Indian languages:
    1. Replaces symbols like "29.4°C" with native words (e.g. in Hindi: "उनतीस दशमलव चार डिग्री सेल्सियस").
    2. Replaces meteorological units (km/h, %, hPa, mm) with native phonetic words.
    3. Cleans conversational filler, markdown formatting, emojis, and thinking tags.
    4. Normalizes punctuation and spacing for clean, natural Edge-TTS prosody.
    Eliminates Edge-TTS American/English accent drift on numbers and units.
    """
    if not text or not text.strip():
        return ""

    short_lang = lang.split("-")[0].lower() if lang else "en"
    effective_unit_lang = short_lang if short_lang in NATIVE_UNIT_LABELS else LANG_NUMBER_MAP_ALIASES.get(short_lang, "en")
    labels = NATIVE_UNIT_LABELS.get(effective_unit_lang, NATIVE_UNIT_LABELS["en"])

    # 1. Clean markdown & conversational filler
    cleaned = strip_conversational_filler(text)
    cleaned = strip_markdown_and_artifacts(cleaned)
    cleaned = strip_conversational_filler(cleaned)

    # 2. Match numbers attached to units and replace both number and unit with native words
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*(?:°C|degC|celsius)", labels["celsius"]),
        (r"(\d+(?:\.\d+)?)\s*(?:°F|fahrenheit)", labels["fahrenheit"]),
        (r"(\d+(?:\.\d+)?)\s*(?:km/h|kmph|kmh)", labels["kmh"]),
        (r"(\d+(?:\.\d+)?)\s*(?:m/s|mps)", labels["ms"]),
        (r"(\d+(?:\.\d+)?)\s*%", labels["percent"]),
        (r"(\d+(?:\.\d+)?)\s*hPa", labels["hpa"]),
        (r"(\d+(?:\.\d+)?)\s*mm", labels["mm"]),
    ]

    for pattern, unit_label in patterns:
        cleaned = re.sub(
            pattern,
            lambda m, u=unit_label: f"{convert_number_to_words(m.group(1), short_lang)} {u}",
            cleaned,
            flags=re.IGNORECASE,
        )

    # 3. Clean remaining raw units if any left without number
    cleaned = re.sub(r"°C", " " + labels["celsius"] + " ", cleaned)
    cleaned = re.sub(r"°F", " " + labels["fahrenheit"] + " ", cleaned)
    cleaned = re.sub(r"km/h", " " + labels["kmh"] + " ", cleaned)
    cleaned = re.sub(r"%", " " + labels["percent"] + " ", cleaned)

    # 4. Spacing and punctuation normalization
    cleaned = re.sub(r"[\r\n]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*([,;:!?।])\s*", r"\1 ", cleaned)
    cleaned = re.sub(r"(?<!\d)\s*\.\s*(?!\d)", ". ", cleaned)
    cleaned = re.sub(r"[,;]\s*[,;]+", ",", cleaned)
    cleaned = re.sub(r"\.\s*\.+", ".", cleaned)
    cleaned = re.sub(r",\s*\.", ".", cleaned)
    cleaned = re.sub(r"-\s*-+", " ", cleaned)
    cleaned = cleaned.strip(" ,-–—\t\r\n")

    if not cleaned:
        return ""

    if cleaned[-1] not in ".!?।":
        if short_lang in ("hi", "bn", "mr", "ne", "kok", "mai", "doi", "brx", "sa"):
            cleaned += "।"
        else:
            cleaned += "."

    return cleaned


def normalize_for_tts(text: str, lang_code: str = "en") -> str:
    """Regional Speech Normalization alias forwarding to prepare_for_tts."""
    return prepare_for_tts(text, lang=lang_code)


def clean_bot_response(text: str, lang_code: str = "en") -> str:
    """Entry point for TTS preparation."""
    return prepare_for_tts(text, lang=lang_code)


def translate_units_to_native(text: str, lang: str = "ur") -> str:
    """
    Task 3: Unit Translation Dictionary & Normalizer.
    Replaces numbers and meteorological units with native phonetic words.
    For Odia: automatically converts to phonetic Devanagari so Edge-TTS can pronounce it.
    Ensures voice output is 100% native.
    """
    if not text:
        return ""
    short_lang = (lang or "ur").split("-")[0].lower()
    res = prepare_for_tts(text, lang=short_lang)
    # If Odia, convert script characters phonetically so hi-IN-SwaraNeural synthesizes without error
    if short_lang == "or" or any(0x0B00 <= ord(c) <= 0x0B7F for c in res):
        res = odia_to_phonetic_devanagari(res)
    return res


def expand_units_for_language(text: str, lang_code: str = "en") -> str:
    """Compatibility alias forwarding to prepare_for_tts."""
    return prepare_for_tts(text, lang=lang_code)


GOOGLE_TRANSLATOR_LANG_MAP: dict[str, str] = {
    "kok": "gom",       # Google Translate uses Goan Konkani (gom)
    "mni": "mni-Mtei",  # Google Translate uses Meitei script for Manipuri
}


INDIC_LANG_FULL_NAMES: dict[str, str] = {
    "brx": "Bodo (in Devanagari script)",
    "ne": "Nepali",
    "kok": "Konkani (in Devanagari script)",
    "mai": "Maithili",
    "doi": "Dogri",
    "sat": "Santali",
    "mni": "Manipuri",
    "as": "Assamese",
    "or": "Odia",
    "sa": "Sanskrit",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "ks": "Kashmiri",
    "sd": "Sindhi",
}


def gemini_translate_fallback(text: str, source_lang: str, target_lang: str = "en") -> str | None:
    """Gemini Flash fast fallback translation for Indic languages not supported by deep-translator or when rate-limited."""
    try:
        import os
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        from langchain_google_genai import ChatGoogleGenerativeAI

        tgt_name = INDIC_LANG_FULL_NAMES.get(target_lang, target_lang)
        src_name = INDIC_LANG_FULL_NAMES.get(source_lang, source_lang)

        models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]
        for m in models_to_try:
            try:
                llm = ChatGoogleGenerativeAI(
                    model=m,
                    google_api_key=api_key,
                    max_retries=1,
                    timeout=15,
                )
                prompt = (
                    f"Translate the following emergency meteorological alert from {src_name} into {tgt_name}.\n"
                    f"Output ONLY the direct translated sentence in the native script. "
                    f"Do NOT include any conversational filler, markdown codeblocks, notes, pronunciation guides, or English text:\n\n{text}"
                )
                res = llm.invoke(prompt)
                content = getattr(res, "content", "")
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            parts.append(item["text"])
                        elif isinstance(item, str):
                            parts.append(item)
                    extracted = " ".join(parts).strip()
                else:
                    extracted = str(content).strip()

                if extracted:
                    # Clean any leading/trailing explanatory notes or formatting
                    lines = [l.strip() for l in extracted.split("\n") if l.strip() and not l.strip().startswith(("*", "#", "`", "(", "["))]
                    cleaned_res = " ".join(lines) if lines else extracted
                    if cleaned_res and cleaned_res.strip().lower() != text.strip().lower():
                        return cleaned_res.strip()
            except Exception as exc:
                logger.debug("Gemini model %s translation error: %s", m, exc)
                continue
    except Exception as e:
        logger.debug("Gemini fallback translation notice: %s", e)
    return None


def safe_translate(text: str, source_lang: str, target_lang: str, input_lang: str | None = None) -> str:
    """
    Translate text with multi-engine fallback:
    GoogleTranslator -> MyMemoryTranslator -> Gemini Flash -> original text (passthrough).
    Enforces Linguistic Lock against language drift (e.g. bn -> mr).
    """
    if not text:
        return ""

    src = source_lang.split("-")[0].lower() if source_lang else "en"
    tgt = target_lang.split("-")[0].lower() if target_lang else "en"
    inp = input_lang.split("-")[0].lower() if input_lang else None

    # Task 3 Check: If input text or input_lang is Bengali and target is Marathi:
    has_bengali_text = (VoiceCleaner.detect_script(text) == "bn")
    if (tgt == "mr" and inp == "bn") or (tgt == "mr" and src == "bn") or (tgt == "mr" and has_bengali_text):
        warnings.warn("Potential Language Drift Detected. Reverting to BN.", category=UserWarning)
        logger.warning(
            "🚨 [LINGUISTIC DRIFT PREVENTED] Potential Language Drift Detected: target='mr' with Bengali input. Reverting target to 'bn'."
        )
        tgt = "bn"

    if src == tgt:
        return text

    # Special handling: Bodo ('brx') is not supported in deep-translator; route directly to Gemini Flash
    if tgt == "brx" or src == "brx":
        gemini_res = gemini_translate_fallback(text, source_lang=src, target_lang=tgt)
        if gemini_res:
            return gemini_res

    # Map language codes for GoogleTranslator
    src_mapped = GOOGLE_TRANSLATOR_LANG_MAP.get(src, src)
    tgt_mapped = GOOGLE_TRANSLATOR_LANG_MAP.get(tgt, tgt)

    # Engine 1: Google Translator
    if GoogleTranslator is not None and tgt != "brx" and src != "brx":
        try:
            result = GoogleTranslator(source=src_mapped, target=tgt_mapped).translate(text)
            if result and result.strip() and result.strip().lower() != text.strip().lower():
                return result
        except Exception as gt_err:
            logger.debug("GoogleTranslator error for %s -> %s: %s", src, tgt, gt_err)

    # Engine 2: MyMemory Translator
    try:
        src_tag = f"{src}-IN" if len(src) == 2 else src
        tgt_tag = f"{tgt}-IN" if len(tgt) == 2 else tgt
        result = MyMemoryTranslator(source=src_tag, target=tgt_tag).translate(text)
        if result and result.strip() and result.strip().lower() != text.strip().lower():
            return result
    except Exception as mm_err:
        logger.debug("MyMemoryTranslator error for %s -> %s: %s", src, tgt, mm_err)

    # Engine 3: Gemini Flash Fast Translation Fallback (All 22 scheduled Indian languages)
    gemini_res = gemini_translate_fallback(text, source_lang=src, target_lang=tgt)
    if gemini_res:
        return gemini_res

    return text
