"""
Multi-Script Unicode Guard, Universal Indian Script Normalizer & Language Resolver for WeatherGPT.

Provides Unicode script validation, purity checks, language/script metadata, and
Universal Indian Script Normalization across all 22 scheduled Indian languages and English.
"""
import logging
import re
import unicodedata
from typing import NamedTuple

logger = logging.getLogger(__name__)

class ScriptDefinition(NamedTuple):
    lang_code: str
    language_name: str
    script_name: str
    script_family: str
    unicode_ranges: list[tuple[int, int]]


# ---------------------------------------------------------------------------
# SCRIPT FAMILIES & UNICODE RANGES (Universal Indian Script Normalizer)
#
# Shared script families prevent false-positive SCRIPT_MISMATCH errors for languages
# sharing the same script (e.g., Devanagari shared by Marathi, Hindi, Sanskrit, Konkani).
# ---------------------------------------------------------------------------

SCRIPT_FAMILIES: dict[str, list[tuple[int, int]]] = {
    "Devanagari": [
        (0x0900, 0x097F),  # Devanagari Standard (includes Marathi ळ, ऱ, ॲ, etc.)
        (0xA8E0, 0xA8FF),  # Devanagari Extended
        (0x1CD0, 0x1CFF),  # Vedic Extensions
    ],
    "Bengali": [
        (0x0980, 0x09FF),  # Bengali & Assamese (includes ৰ, ৱ)
    ],
    "Gurmukhi": [
        (0x0A00, 0x0A7F),  # Punjabi Gurmukhi
    ],
    "Gujarati": [
        (0x0A80, 0x0AFF),  # Gujarati
    ],
    "Odia": [
        (0x0B00, 0x0B7F),  # Odia
    ],
    "Tamil": [
        (0x0B80, 0x0BFF),  # Tamil
    ],
    "Telugu": [
        (0x0C00, 0x0C7F),  # Telugu
    ],
    "Kannada": [
        (0x0C80, 0x0CFF),  # Kannada
    ],
    "Malayalam": [
        (0x0D00, 0x0D7F),  # Malayalam
    ],
    "Perso-Arabic": [
        (0x0600, 0x06FF),  # Arabic
        (0x0750, 0x077F),  # Arabic Supplement
        (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    ],
    "Ol Chiki": [
        (0x1C50, 0x1C7F),  # Santali Ol Chiki
    ],
    "Meitei Mayek": [
        (0xABC0, 0xABFF),  # Meetei Mayek
        (0xAAE0, 0xAAFF),  # Meetei Mayek Extensions
    ],
    "Latin": [
        (0x0041, 0x005A),  # Latin A-Z
        (0x0061, 0x007A),  # Latin a-z
    ],
}

# ---------------------------------------------------------------------------
# SCRIPT REGISTRY — All 22 Scheduled Indian Languages + English
# ---------------------------------------------------------------------------

SCRIPT_REGISTRY: dict[str, ScriptDefinition] = {
    # --- Devanagari Family ---
    "hi": ScriptDefinition(
        lang_code="hi",
        language_name="Hindi",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),
    "mr": ScriptDefinition(
        lang_code="mr",
        language_name="Marathi",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),
    "sa": ScriptDefinition(
        lang_code="sa",
        language_name="Sanskrit",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),
    "ne": ScriptDefinition(
        lang_code="ne",
        language_name="Nepali",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),
    "kok": ScriptDefinition(
        lang_code="kok",
        language_name="Konkani",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),
    "mai": ScriptDefinition(
        lang_code="mai",
        language_name="Maithili",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),
    "brx": ScriptDefinition(
        lang_code="brx",
        language_name="Bodo",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),
    "doi": ScriptDefinition(
        lang_code="doi",
        language_name="Dogri",
        script_name="Devanagari",
        script_family="Devanagari",
        unicode_ranges=SCRIPT_FAMILIES["Devanagari"],
    ),

    # --- Bengali / Assamese Family ---
    "bn": ScriptDefinition(
        lang_code="bn",
        language_name="Bengali",
        script_name="Bengali",
        script_family="Bengali",
        unicode_ranges=SCRIPT_FAMILIES["Bengali"],
    ),
    "as": ScriptDefinition(
        lang_code="as",
        language_name="Assamese",
        script_name="Bengali/Assamese",
        script_family="Bengali",
        unicode_ranges=SCRIPT_FAMILIES["Bengali"],
    ),
    "mni": ScriptDefinition(
        lang_code="mni",
        language_name="Manipuri",
        script_name="Bengali / Meitei",
        script_family="Bengali",
        unicode_ranges=SCRIPT_FAMILIES["Bengali"] + SCRIPT_FAMILIES["Meitei Mayek"],
    ),

    # --- Other Major Indian Regional Scripts ---
    "pa": ScriptDefinition(
        lang_code="pa",
        language_name="Punjabi",
        script_name="Gurmukhi",
        script_family="Gurmukhi",
        unicode_ranges=SCRIPT_FAMILIES["Gurmukhi"],
    ),
    "gu": ScriptDefinition(
        lang_code="gu",
        language_name="Gujarati",
        script_name="Gujarati",
        script_family="Gujarati",
        unicode_ranges=SCRIPT_FAMILIES["Gujarati"],
    ),
    "or": ScriptDefinition(
        lang_code="or",
        language_name="Odia",
        script_name="Odia",
        script_family="Odia",
        unicode_ranges=SCRIPT_FAMILIES["Odia"],
    ),
    "ta": ScriptDefinition(
        lang_code="ta",
        language_name="Tamil",
        script_name="Tamil",
        script_family="Tamil",
        unicode_ranges=SCRIPT_FAMILIES["Tamil"],
    ),
    "te": ScriptDefinition(
        lang_code="te",
        language_name="Telugu",
        script_name="Telugu",
        script_family="Telugu",
        unicode_ranges=SCRIPT_FAMILIES["Telugu"],
    ),
    "kn": ScriptDefinition(
        lang_code="kn",
        language_name="Kannada",
        script_name="Kannada",
        script_family="Kannada",
        unicode_ranges=SCRIPT_FAMILIES["Kannada"],
    ),
    "ml": ScriptDefinition(
        lang_code="ml",
        language_name="Malayalam",
        script_name="Malayalam",
        script_family="Malayalam",
        unicode_ranges=SCRIPT_FAMILIES["Malayalam"],
    ),

    # --- Perso-Arabic Family ---
    "ur": ScriptDefinition(
        lang_code="ur",
        language_name="Urdu",
        script_name="Perso-Arabic",
        script_family="Perso-Arabic",
        unicode_ranges=SCRIPT_FAMILIES["Perso-Arabic"],
    ),
    "ks": ScriptDefinition(
        lang_code="ks",
        language_name="Kashmiri",
        script_name="Perso-Arabic / Devanagari",
        script_family="Perso-Arabic",
        unicode_ranges=SCRIPT_FAMILIES["Perso-Arabic"] + SCRIPT_FAMILIES["Devanagari"],
    ),
    "sd": ScriptDefinition(
        lang_code="sd",
        language_name="Sindhi",
        script_name="Perso-Arabic / Devanagari",
        script_family="Perso-Arabic",
        unicode_ranges=SCRIPT_FAMILIES["Perso-Arabic"] + SCRIPT_FAMILIES["Devanagari"],
    ),

    # --- Santali (Ol Chiki / Devanagari) ---
    "sat": ScriptDefinition(
        lang_code="sat",
        language_name="Santali",
        script_name="Ol Chiki / Devanagari",
        script_family="Ol Chiki",
        unicode_ranges=SCRIPT_FAMILIES["Ol Chiki"] + SCRIPT_FAMILIES["Devanagari"],
    ),

    # --- Latin / English ---
    "en": ScriptDefinition(
        lang_code="en",
        language_name="English",
        script_name="Latin",
        script_family="Latin",
        unicode_ranges=SCRIPT_FAMILIES["Latin"],
    ),
}


def is_char_in_script(char: str, lang_code: str) -> bool:
    """Check if a character falls within the Unicode ranges for the script family of lang_code.
    
    Universal Indian Script Normalizer: Allows all characters in the entire script family
    (e.g., \\u0900-\\u097F Devanagari) for any language sharing that script (Marathi, Hindi, Sanskrit, Konkani).
    """
    norm = lang_code.split("-")[0].lower() if lang_code else "en"
    script_def = SCRIPT_REGISTRY.get(norm)
    if not script_def:
        return True

    code = ord(char)
    # Check against the language's full script family ranges
    for start, end in script_def.unicode_ranges:
        if start <= code <= end:
            return True
    return False


def calculate_script_purity(text: str, lang_code: str) -> float:
    """
    Calculate the ratio of characters in *text* belonging to *lang_code*'s script family.
    Punctuation, digits, and whitespace are ignored.
    """
    if not text:
        return 0.0

    norm = lang_code.split("-")[0].lower() if lang_code else "en"
    if norm == "en":
        alpha_chars = [c for c in text if c.isalpha()]
        if not alpha_chars:
            return 1.0
        latin_count = sum(1 for c in alpha_chars if ord(c) < 128)
        return latin_count / len(alpha_chars)

    test_chars = [c for c in text if not c.isspace() and not c.isdigit() and c not in ".,;:!?()[]{}\"'`~@#$%^&*-_=+/\\|<>-–—"]
    if not test_chars:
        return 0.0

    match_count = sum(1 for c in test_chars if is_char_in_script(c, norm))
    return match_count / len(test_chars)


def validate_script_purity(text: str, lang_code: str, threshold: float = 0.30) -> bool:
    """
    Validate that the text contains at least *threshold* (default 30%)
    characters from the expected language's script family.
    """
    if not text or not text.strip():
        return False

    norm = lang_code.split("-")[0].lower() if lang_code else "en"
    if norm == "en":
        return True

    purity = calculate_script_purity(text, norm)
    return purity >= threshold


# -----------------------------------------------------------------------
# CJK (Chinese / Japanese / Korean) Detection Ranges
# Used to catch Whisper "Auto-Detect" hallucinations on noise/silence
# -----------------------------------------------------------------------
CJK_RANGES: list[tuple[int, int]] = [
    (0x3040, 0x309F),   # Hiragana (Japanese, e.g. 浮かたへかるが)
    (0x30A0, 0x30FF),   # Katakana (Japanese)
    (0x31F0, 0x31FF),   # Katakana Phonetic Extensions
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs (Chinese / Kanji)
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF), # CJK Unified Ideographs Extension B
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0xAC00, 0xD7AF),   # Hangul Syllables (Korean)
    (0x1100, 0x11FF),   # Hangul Jamo
]


def contains_cjk_characters(text: str) -> bool:
    """Check if *text* contains any Japanese, Chinese, or Korean Unicode characters."""
    if not text:
        return False
    for char in text:
        code = ord(char)
        for start, end in CJK_RANGES:
            if start <= code <= end:
                return True
    return False


def validate_script_alignment(text: str, expected_lang: str, is_forced: bool = False) -> tuple[bool, str]:
    """
    Multi-Script Unicode Validator (Agnostic Indian Script Normalizer):
    Verifies that *text* strictly aligns with the expected Unicode script family for *expected_lang*.
    Rejects text containing CJK (Japanese/Chinese/Korean) or foreign script characters.

    Allows all characters in \u0900-\u097F for ANY Devanagari language (Marathi, Hindi, Sanskrit, Konkani).
    Does NOT discriminate between Marathi and Hindi Devanagari subsets.

    TASK 3 HARDENING:
    - If expected_lang is a regional Indian language and Whisper returns Latin/Roman script (English letters),
      do NOT reject it. Phonetic Romanized input (e.g. 'Kalker Abu Hawa') is accepted for translation.
    - If is_forced is True (user explicitly selected language), trust Whisper output unless foreign script is found.

    Returns:
        (True, "OK") if aligned.
        (False, "SYS_VOICE > ERROR: SCRIPT_MISMATCH: ...") if mismatched.
    """
    if not text or not text.strip():
        return (False, "SYS_VOICE > ERROR: SCRIPT_MISMATCH: Empty transcription. Please speak clearly.")

    norm = expected_lang.split("-")[0].lower() if expected_lang else "en"
    lang_name, script_name = get_language_and_script_names(norm)

    # 1. Hard-Rejection: Any CJK characters in Indian or English terminal
    if contains_cjk_characters(text):
        return (
            False,
            f"SYS_VOICE > ERROR: SCRIPT_MISMATCH: Detected CJK (Japanese/Chinese) characters "
            f"while expecting {lang_name} ({script_name} script). Please try again."
        )

    # 2. English validation: Must not contain non-ASCII foreign alphabet characters
    if norm == "en":
        for char in text:
            if char.isalpha() and ord(char) > 127:
                return (
                    False,
                    f"SYS_VOICE > ERROR: SCRIPT_MISMATCH: Detected non-English script characters "
                    f"while expecting English. Please try again."
                )
        return (True, "OK")

    # 3. Regional Indian Language validation
    script_def = SCRIPT_REGISTRY.get(norm)
    if not script_def:
        return (True, "OK")

    letters = [c for c in text if c.isalpha()]
    if not letters:
        return (
            False,
            f"SYS_VOICE > ERROR: SCRIPT_MISMATCH: No linguistic characters found for {lang_name}. Please try again."
        )

    # TASK 3: Romanization / Phonetic Acceptance
    # If the user selected a regional Indian language and Whisper returns Latin/Roman letters,
    # accept it so downstream translation can handle phonetic queries (e.g. 'Kalker Abu Hawa').
    if all(ord(c) <= 127 for c in letters):
        return (True, "OK")

    match_count = 0
    foreign_letters = 0
    for char in letters:
        if is_char_in_script(char, norm):
            match_count += 1
        elif ord(char) > 127:
            # Foreign Unicode character outside the target script family
            foreign_letters += 1

    if foreign_letters > 0:
        return (
            False,
            f"SYS_VOICE > ERROR: SCRIPT_MISMATCH: Input contains characters outside allowed {script_name} script "
            f"for {lang_name}. Please try again."
        )

    purity = match_count / len(letters)
    if is_forced or purity >= 0.30:
        return (True, "OK")

    return (
        False,
        f"SYS_VOICE > ERROR: SCRIPT_MISMATCH: Input did not meet 30% script threshold for {lang_name} "
        f"(purity={purity*100:.1f}%). Please speak clearly in {lang_name}."
    )


# ---------------------------------------------------------------------------
# Lexical & Disambiguation Markers for Shared Script Families
# ---------------------------------------------------------------------------
_MARATHI_MARKERS = {
    "आहे", "नाही", "कसे", "कसा", "कशी", "काय", "कधी", "कुठे", "पाऊस", "हवामान",
    "मध्ये", "करा", "होईल", "येथे", "तापमान", "सांगा", "वारं", "वारे", "पुणे", "मुंबई"
}
_HINDI_MARKERS = {
    "है", "नहीं", "कैसा", "कैसी", "कैसे", "क्या", "कब", "कहाँ", "बारिश", "मौसम",
    "में", "करो", "होगा", "यहाँ", "तापमान", "बताओ", "हवा", "दिल्ली"
}
_NEPALI_MARKERS = {
    "छ", "छैन", "कस्तो", "के", "कहिले", "कहाँ", "पानी", "हावा", "मौसम"
}


def disambiguate_devanagari(text: str) -> str:
    """Disambiguate among languages sharing Devanagari using deterministic lexical markers (no langid)."""
    import re
    tokens = set(re.findall(r"[\u0900-\u097F]+", text))
    if tokens:
        mr_matches = len(tokens & _MARATHI_MARKERS)
        hi_matches = len(tokens & _HINDI_MARKERS)
        ne_matches = len(tokens & _NEPALI_MARKERS)

        if mr_matches > hi_matches and mr_matches > ne_matches:
            return "mr"
        if ne_matches > hi_matches and ne_matches > mr_matches:
            return "ne"
        if hi_matches > 0:
            return "hi"

    # Default to Hindi if no explicit regional markers detected
    return "hi"


def get_char_script_family(char: str) -> str | None:
    """Return the family name for a character based on SCRIPT_FAMILIES."""
    code = ord(char)
    for family_name, ranges in SCRIPT_FAMILIES.items():
        for start, end in ranges:
            if start <= code <= end:
                return family_name
    return None


def detect_dominant_script(text: str) -> tuple[str, str, float]:
    """
    Detect the dominant Indian Unicode script family in *text*.
    Completely deterministic — zero langid dependency to prevent false positives.

    Returns:
        (LANGUAGE_CODE, SCRIPT_FAMILY_NAME, PURITY_SCORE)
        e.g. ("mr", "Devanagari", 0.95), ("bn", "Bengali", 1.0), ("en", "Latin", 1.0)
    """
    if not text or not text.strip():
        return ("en", "Latin", 1.0)

    letters = [c for c in text if c.isalpha()]
    total_len = len(letters)
    if total_len == 0:
        return ("en", "Latin", 1.0)

    family_counts: dict[str, int] = {}
    for char in letters:
        family = get_char_script_family(char)
        if family:
            family_counts[family] = family_counts.get(family, 0) + 1

    if not family_counts:
        return ("en", "Latin", 1.0)

    best_family, best_count = max(family_counts.items(), key=lambda item: item[1])
    purity = best_count / total_len

    # Disambiguate language within the identified script family
    if best_family == "Devanagari":
        lang_code = disambiguate_devanagari(text)
        return (lang_code, "Devanagari", purity)

    if best_family == "Bengali":
        # Check for Assamese-specific characters: ৰ (0x09F0) and ৱ (0x09F1)
        if any(c in text for c in ("\u09F0", "\u09F1")):
            return ("as", "Bengali/Assamese", purity)
        return ("bn", "Bengali", purity)

    if best_family == "Gurmukhi":
        return ("pa", "Gurmukhi", purity)
    if best_family == "Gujarati":
        return ("gu", "Gujarati", purity)
    if best_family == "Odia":
        return ("or", "Odia", purity)
    if best_family == "Tamil":
        return ("ta", "Tamil", purity)
    if best_family == "Telugu":
        return ("te", "Telugu", purity)
    if best_family == "Kannada":
        return ("kn", "Kannada", purity)
    if best_family == "Malayalam":
        return ("ml", "Malayalam", purity)
    if best_family == "Perso-Arabic":
        return ("ur", "Perso-Arabic", purity)
    if best_family == "Ol Chiki":
        return ("sat", "Ol Chiki", purity)
    if best_family == "Meitei Mayek":
        return ("mni", "Meitei Mayek", purity)

    return ("en", "Latin", 1.0)


def get_language_and_script_names(lang_code: str) -> tuple[str, str]:
    """Return human-readable (LANGUAGE_NAME, SCRIPT_NAME) for any language code."""
    norm = lang_code.split("-")[0].lower() if lang_code else "en"
    if norm in SCRIPT_REGISTRY:
        s = SCRIPT_REGISTRY[norm]
        return (s.language_name, s.script_name)
    return ("English", "Latin")


def detect_script_language(text: str, min_purity: float = 0.20) -> str | None:
    """Detect regional Indian language code from unicode script ranges.
    Returns language code (e.g. 'mr', 'hi', 'bn', etc.) if purity >= min_purity, else None.
    """
    if not text:
        return None
    lang, _script, purity = detect_dominant_script(text)
    if lang != "en" and purity >= min_purity:
        return lang
    return None

