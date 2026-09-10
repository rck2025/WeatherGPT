"""Dynamic Date Extraction and Meteorological Brain Interface."""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from dateutil import parser
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


def extract_target_date(user_query: str, ref_date: Optional[datetime] = None) -> Optional[str]:
    """
    Extract a structured YYYY-MM-DD target date from natural language queries.
    Handles:
      - Explicit dates: 'June 10, 2024', 'August 15, 1947', '2020-05-20', '15th August 1947'
      - Relative timeframes: 'August 15th last year', '3 days ago', 'last Tuesday', 'yesterday'
      - Event markers: 'Cyclone Amphan (May 20, 2020)'
      - Unspecified past queries: defaults to yesterday when past intent is detected.
    
    Returns:
        YYYY-MM-DD string or None if query is not a past date query.
    """
    if not user_query:
        return None

    if ref_date is None:
        ref_date = datetime.now()

    q = user_query.strip()
    q_lower = q.lower()

    # ── 1. Relative Keywords: 'yesterday', 'day before yesterday' across 15 languages ──
    if "day before yesterday" in q_lower or "day before" in q_lower or "parso" in q_lower or "পরশু" in q_lower:
        return (ref_date - timedelta(days=2)).strftime("%Y-%m-%d")

    # Hindi & Urdu 'Kal' with past tense copula (था, थी, थे, تھا etc.)
    if "कल" in q_lower and any(w in q_lower for w in ["था", "थी", "थे", "कैसा", "बीता", "पिछल"]):
        return (ref_date - timedelta(days=1)).strftime("%Y-%m-%d")
    if "کل" in q_lower and any(w in q_lower for w in ["تھا", "تھی", "تھے", "کیسا", "گزشتہ"]):
        return (ref_date - timedelta(days=1)).strftime("%Y-%m-%d")

    yesterday_patterns = [
        "yesterday", "beeta kal", "pichle kal", "kal kitni", "kal kaisa", "kal kaisa tha", "kal tha", "kal ka mausam",
        "গতকাল", "গত কাল", "goto kal", "நேற்று", "netru", "నిన్న", "ninna", "काल",
        "ગઈકાલે", "ગઈ કાલે", "gaikale", "ನಿನ್ನೆ", "ninne", "ഇന്നലെ", "innale",
        "ਕੱਲ੍ਹ", "ਕੱਲ", "kallh", "ଗତକାଲି", "gatakali", "কালি", "kali", "हिजो", "hijo",
        "ह्यः", "hya", "گزشتہ کل", "کل کیसा था"
    ]
    if any(yp in q_lower for yp in yesterday_patterns):
        if not any(fw in q_lower for fw in ["rahega", "hoga", "hogi", "hoge", "aayega", "karega", "will", "future", "forecast", "outlook"]):
            return (ref_date - timedelta(days=1)).strftime("%Y-%m-%d")

    # ── 2. Relative Elapsed Offsets: 'N days/weeks/months/years ago' ──
    m_days = re.search(r"(\d+)\s*days?\s*ago", q_lower)
    if m_days:
        n = int(m_days.group(1))
        return (ref_date - timedelta(days=n)).strftime("%Y-%m-%d")

    m_weeks = re.search(r"(\d+)\s*weeks?\s*ago", q_lower)
    if m_weeks:
        n = int(m_weeks.group(1))
        return (ref_date - timedelta(weeks=n)).strftime("%Y-%m-%d")

    m_months = re.search(r"(\d+)\s*months?\s*ago", q_lower)
    if m_months:
        n = int(m_months.group(1))
        return (ref_date - relativedelta(months=n)).strftime("%Y-%m-%d")

    m_years = re.search(r"(\d+)\s*years?\s*ago", q_lower)
    if m_years:
        n = int(m_years.group(1))
        return (ref_date - relativedelta(years=n)).strftime("%Y-%m-%d")

    # ── 3. Weekday Offsets: 'last Tuesday', 'last Friday', etc. ──
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    m_weekday = re.search(
        r"last\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        q_lower
    )
    if m_weekday:
        target_weekday = weekdays[m_weekday.group(1)]
        days_back = (ref_date.weekday() - target_weekday) % 7
        if days_back == 0:
            days_back = 7
        return (ref_date - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # ── 4. '<Month> <Day> last year' e.g. 'August 15th last year' ──
    m_last_year = re.search(
        r"([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+last\s+year",
        q_lower
    )
    if m_last_year:
        month_str, day_str = m_last_year.group(1), m_last_year.group(2)
        try:
            parsed = parser.parse(f"{month_str} {day_str} {ref_date.year - 1}")
            return parsed.strftime("%Y-%m-%d")
        except Exception:
            pass

    # ── 5. Standard ISO / Hyphenated / Slashed Dates (YYYY-MM-DD) ──
    m_iso = re.search(r"\b(19\d\d|20\d\d)[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b", q)
    if m_iso:
        y, m, d = m_iso.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # ── 6. Explicit Month-Day-Year or Day-Month-Year Formats ──
    # Note: Strip ordinal indicators attached to numbers (e.g. 15th -> 15) without touching words like August!
    clean_ordinals = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", q, flags=re.IGNORECASE)

    # Search for explicit patterns containing month names and 4-digit years (1940 - 2099)
    month_regex = (
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    )

    # Case A: Month Day, Year (e.g. "August 15, 1947", "May 20, 2020", "Jan 1, 2020")
    m_mdy = re.search(
        rf"\b({month_regex}\s+[0-3]?\d[,\s]+(19\d\d|20\d\d))\b",
        clean_ordinals,
        re.IGNORECASE
    )
    if m_mdy:
        try:
            parsed = parser.parse(m_mdy.group(1), default=ref_date)
            return f"{parsed.year:04d}-{parsed.month:02d}-{parsed.day:02d}"
        except Exception:
            pass

    # Case B: Day Month Year (e.g. "10 June 2024", "15 August 1947")
    m_dmy = re.search(
        rf"\b([0-3]?\d\s+(?:of\s+)?{month_regex}[,\s]+(19\d\d|20\d\d))\b",
        clean_ordinals,
        re.IGNORECASE
    )
    if m_dmy:
        try:
            parsed = parser.parse(m_dmy.group(1), default=ref_date)
            return f"{parsed.year:04d}-{parsed.month:02d}-{parsed.day:02d}"
        except Exception:
            pass

    # Case C: Month Day without explicit year (e.g. "September 4th", "Sept 4", "August 15")
    m_md_noyear = re.search(
        rf"\b({month_regex}\s+[0-3]?\d)\b",
        clean_ordinals,
        re.IGNORECASE
    )
    if m_md_noyear:
        try:
            parsed = parser.parse(m_md_noyear.group(1), default=ref_date)
            year = ref_date.year
            cand = parsed.replace(year=year).date()
            if cand > ref_date.date():
                year -= 1
            return f"{year:04d}-{parsed.month:02d}-{parsed.day:02d}"
        except Exception:
            pass

    # Case D: Day Month without explicit year (e.g. "4th September", "15 August", "4th of September")
    m_dm_noyear = re.search(
        rf"\b([0-3]?\d\s+(?:of\s+)?{month_regex})\b",
        clean_ordinals,
        re.IGNORECASE
    )
    if m_dm_noyear:
        try:
            parsed = parser.parse(m_dm_noyear.group(1), default=ref_date)
            year = ref_date.year
            cand = parsed.replace(year=year).date()
            if cand > ref_date.date():
                year -= 1
            return f"{year:04d}-{parsed.month:02d}-{parsed.day:02d}"
        except Exception:
            pass

    # Case E: Fuzzy dateutil parse if a distinct 4-digit past year is present
    year_match = re.search(r"\b(19\d\d|20\d\d)\b", q)
    if year_match:
        try:
            parsed = parser.parse(clean_ordinals, fuzzy=True, default=ref_date)
            # Ensure the parsed date actually reflects the extracted year
            if str(parsed.year) == year_match.group(1):
                return f"{parsed.year:04d}-{parsed.month:02d}-{parsed.day:02d}"
        except Exception:
            pass

    # ── 7. 'last week' or 'last month' or 'last year' ──
    if "last week" in q_lower:
        return (ref_date - timedelta(days=7)).strftime("%Y-%m-%d")
    if "last month" in q_lower:
        return (ref_date - relativedelta(months=1)).strftime("%Y-%m-%d")

    # ── 8. Default: If query expresses PAST intent without explicit date, default to yesterday ──
    past_triggers = [
        "history", "historical", "past", "archive", "archived",
        "was the weather", "did it rain", "how much rain fell", "recorded",
        "records show", "how hot was", "how cold was", "past weather",
        "previous day", "earlier this week", "cyclone amphan", "cyclone fani"
    ]
    if any(pt in q_lower for pt in past_triggers):
        return (ref_date - timedelta(days=1)).strftime("%Y-%m-%d")

    return None


# ── Indic Script & Multilingual Temporal Slot Extraction ──
INDIC_NUMERAL_MAP = {
    # Devanagari (Hindi, Marathi, Nepali, Sanskrit, Maithili, Bodo, Dogri)
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
    # Bengali / Assamese / Manipuri
    '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4', '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9',
    # Gurmukhi (Punjabi)
    '੦': '0', '੧': '1', '੨': '2', '੩': '3', '੪': '4', '੫': '5', '੬': '6', '੭': '7', '੮': '8', '੯': '9',
    # Gujarati
    '૦': '0', '૧': '1', '૨': '2', '૩': '3', '૪': '4', '૫': '5', '૬': '6', '૭': '7', '૮': '8', '૯': '9',
    # Odia
    '୦': '0', '୧': '1', '୨': '2', '୩': '3', '୪': '4', '୫': '5', '୬': '6', '୭': '7', '୮': '8', '୯': '9',
    # Tamil
    '௦': '0', '௧': '1', '௨': '2', '௩': '3', '௪': '4', '௫': '5', '௬': '6', '௭': '7', '௮': '8', '௯': '9',
    # Telugu
    '౦': '0', '౧': '1', '౨': '2', '౩': '3', '౪': '4', '౫': '5', '౬': '6', '౭': '7', '౮': '8', '౯': '9',
    # Kannada
    '೦': '0', '೧': '1', '೨': '2', '೩': '3', '೪': '4', '೫': '5', '೬': '6', '೭': '7', '೮': '8', '೯': '9',
    # Malayalam
    '൦': '0', '൧': '1', '൨': '2', '൩': '3', '൪': '4', '൫': '5', '൬': '6', '൭': '7', '൮': '8', '൯': '9',
    # Perso-Arabic / Urdu / Kashmiri / Sindhi
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
}

def normalize_indic_digits(text: str) -> str:
    """Normalize Indian and Perso-Arabic script digits to standard ASCII numerals (0-9)."""
    if not text:
        return ""
    return "".join(INDIC_NUMERAL_MAP.get(ch, ch) for ch in text)


MINUTES_KEYWORDS = (
    r"(?:mins?|minutes?|m\b|"
    r"मिनट|मिनिट|मिनिटे|मिनिटात|मिनेट|निमेष(?:ाः|े|ेषु|ान्)?|"  # Devanagari (Hindi, Marathi, Nepali, Sanskrit)
    r"মিনিট(?:ে)?|মিনিটত|"             # Bengali / Assamese
    r"ਮਿੰਟ(?:ਾਂ)?|"                     # Gurmukhi
    r"મિનિટ(?:માં)?|"                  # Gujarati
    r"ମିନିଟ(?:ରେ)?|"                   # Odia
    r"நிமிட(?:ம்|ங்கள்|ங்களில்)?|"      # Tamil
    r"నిమిషా(?:లు|ల్లో)?|"             # Telugu
    r"ನಿಮಿಷ(?:ಗಳು|ಗಳಲ್ಲಿ)?|"           # Kannada
    r"മിനിറ്റ(?:്|ിൽ|ുകൾ)?|"            # Malayalam
    r"منٹ(?:وں)?)"                      # Urdu
)

HOURS_KEYWORDS = (
    r"(?:hrs?|hours?|h\b|"
    r"ghante|ghanta|ghanto|"           # Romanized Hindi/Urdu
    r"घंटे|घंटा|घण्टा|घन्टा|"          # Devanagari
    r"तास|तासात|"                       # Marathi
    r"ঘণ্টা|ঘন্টা|"                     # Bengali / Assamese
    r"ਘੰਟੇ|ਘੰਟਾ|"                       # Gurmukhi
    r"કલાક|"                           # Gujarati
    r"ଘଣ୍ଟା|"                          # Odia
    r"மணி(?:நேரம்)?|"                  # Tamil
    r"గంట(?:లు)?|"                     # Telugu
    r"ಗಂಟೆ(?:ಗಳು)?|"                   # Kannada
    r"മണിക്കൂർ|"                       # Malayalam
    r"گھنٹے|گھنٹہ|گھنٹوں)"              # Urdu
)

WORD_TO_MINUTES = {
    "one": 1, "ek": 1, "एक": 1, "एक": 1, "এক": 1, "ଏକ": 1, "ஒரு": 1, "ఒక": 1, "ಒಂದು": 1, "ഒരു": 1,
    "five": 5, "paanch": 5, "पांच": 5, "पाच": 5, "পাঁচ": 5,
    "ten": 10, "dus": 10, "दश": 10, "दस": 10, "দশ": 10,
    "fifteen": 15, "pandrah": 15, "पंद्रह": 15, "পনেরো": 15, "பதினைந்து": 15,
    "twenty": 20, "bees": 20, "बीस": 20, "কুড়ি": 20, "இருபது": 20,
    "thirty": 30, "tees": 30, "तीस": 30, "ত্রিশ": 30, "முப்பது": 30,
    "forty five": 45, "forty-five": 45, "paitalis": 45, "पैंतालीस": 45,
}


def get_query_time_offset(query: str) -> Optional[int]:
    """
    Extract temporal minute-offset from natural language queries across all 15 Indian languages + English.
    Handles:
      - 1-minute tactical radar nowcasting (e.g. 'in 1 minute', 'Will it rain in 1 min?', 'ek minute mein')
      - 15-minute NWP slot filling (e.g. 'next 15 mins', '15 minute mein', '१५ मिनट', '১৫ মিনিট')
      - Hourly slots (e.g. 'in 2 hours', '2 ghante', '२ तास', '२ કલાક')
      - Conversational offsets ('half an hour', 'aadha ghanta', 'quarter hour')
      - Day offsets ('tomorrow', 'kal' -> 1440)
    
    Returns:
        Minute integer offset (e.g. 1, 15, 30, 45, 60, 120, 1440) or None if no specific time slot.
    """
    if not query:
        return None

    norm = normalize_indic_digits(query.strip())
    q_low = norm.lower()

    # 1. Conversational half-hour, quarter-hour, 90-min offsets (without trailing \b for Indic script combinations)
    if re.search(
        r"(?:\b(?:half\s+(?:an?\s+)?hour|half\s*hour|aadha\s+ghant[ae]|aadhe\s+ghant[ae]|adho\s+kalak|ardha\s+taas)|"
        r"आधा\s+घंटा|आधे\s+घंटे|अर्धा\s+तास|আধা\s+ঘণ্টা|அரை\s+மணி)",
        q_low,
    ):
        return 30

    if re.search(
        r"(?:\b(?:quarter\s+(?:of\s+an?\s+)?hour|paun\s+ghant[ae])|कालब\s+तास|पाव\s+तास)",
        q_low,
    ):
        return 15

    if re.search(
        r"(?:\b(?:dedh|derh)\s+ghant[ae]|दीड\s+तास|দেড়\s+ঘণ্টা)",
        q_low,
    ):
        return 90

    # 2. Number + Minutes Keyword (e.g. '1 minute', '15 minutes', '१५ मिनट', '১৫ মিনিট')
    m_min = re.search(rf"(\d+)\s*(?:-|–)?\s*{MINUTES_KEYWORDS}", norm, re.IGNORECASE)
    if m_min:
        return int(m_min.group(1))

    # 3. Number + Hours Keyword (e.g. '2 hours', '2 ghante', '२ तास', '२ કલાક')
    m_hr = re.search(rf"(\d+)\s*(?:-|–)?\s*{HOURS_KEYWORDS}", norm, re.IGNORECASE)
    if m_hr:
        return int(m_hr.group(1)) * 60

    # 4. Spelled-out word numbers + Minutes (e.g. 'one minute', 'ek minute')
    for word_num, minute_val in WORD_TO_MINUTES.items():
        if re.search(rf"(?:\b{word_num}\b|{word_num})\s+{MINUTES_KEYWORDS}", q_low):
            return minute_val

    # 5. Spelled-out word numbers + Hours
    if re.search(rf"(?:\b(?:an?|one|ek|next|agle|agli)\b|एक|এক|ଏକ|ஒரு|ఒక|ಒಂದು|ഒരു|अगले|पुढील|આગામી|அடுத்த|తర్వాత|ಮುಂದಿನ|পরবর্তী|آئندہ)\s+{HOURS_KEYWORDS}", q_low):
        return 60
    if re.search(rf"(?:\b(?:two|do)\b|दोन|दो|দুই|ଦୁଇ|இரண்டு|రెండు|ಎರಡು|രണ്ട്)\s+{HOURS_KEYWORDS}", q_low):
        return 120
    if re.search(rf"(?:\b(?:three|teen)\b|तीन|তিন|ତିନି|மூன்று|మూడు|ಮೂರು|മൂന്ന്)\s+{HOURS_KEYWORDS}", q_low):
        return 180

    # 6. Tomorrow / Next-Day keyword
    if re.search(r"(?:\b(?:tomorrow|kal)\b|आगामी\s+दिन|আগামীকাল|நாளை|రేపు|ನಾಳೆ|നാളെ)", q_low) and not any(
        p in q_low for p in ["yesterday", "beeta kal", "pichle kal"]
    ):
        return 1440

    return None


# ------------------------------------------------------------------
# MULTI-LINGUAL TEMPORAL DICTIONARY (ALL 15 SCHEDULED LANGUAGES)
# ------------------------------------------------------------------

TEMPORAL_MARKERS: dict[str, dict[str, list[str]]] = {
    "en": {
        "past": ["previous", "ago", "last", "past", "prior", "earlier", "was", "were", "did", "had", "recorded"],
        "future": ["next", "in", "will", "upcoming", "within", "after", "coming", "expecting", "forecast", "ahead"],
    },
    "hi": {
        "past": ["पहले", "बीता", "बीते", "था", "थी", "थे", "पिछला", "पिछले", "पिछली", "पूर्व", "pehle", "pahle", "beeta", "beete", "pichle", "pichla", "tha", "thi", "thhey"],
        "future": ["अगले", "अगला", "अगली", "बाद", "होगा", "होगी", "होंगे", "आने वाले", "में", "आगामी", "agle", "agla", "baad", "hoga", "hogi", "aane wala"],
    },
    "bn": {
        "past": ["আগে", "অতীত", "ছিল", "পূর্বে", "গত", "হয়েছিল", "আগের", "aage", "chilo", "goto", "purbe"],
        "future": ["পরে", "আগামী", "হবে", "পরবর্তী", "আসন্ন", "সামনে", "pore", "hobe", "poroborti", "agami"],
    },
    "ta": {
        "past": ["முன்பு", "கடந்த", "முன்னர்", "இருந்தது", "நடந்தது", "முந்தைய", "munbu", "kadandha", "munnar"],
        "future": ["அடுத்த", "பிறகு", "பின்", "வரும்", "இருக்கும்", "வரவிருக்கும்", "adutha", "piragu", "pin"],
    },
    "te": {
        "past": ["క్రితం", "ముందు", "గత", "ఉండినది", "జరిగినది", "మునుపటి", "kritham", "mundhu", "gatha"],
        "future": ["తర్వాత", "రాబోయే", "తరువాత", "ఉంటుంది", "వచ్చే", "రానున్న", "tharvatha", "raboye", "vache"],
    },
    "mr": {
        "past": ["पूर्वी", "मागील", "होता", "होती", "होते", "गेल्या", "आधी", "purvi", "magil", "hota", "hoti", "aadhi"],
        "future": ["पुढील", "नंतर", "होईल", "येणाऱ्या", "येत्या", "पुढे", "pudhil", "nantar", "hoil", "yenarya"],
    },
    "gu": {
        "past": ["પહેલાં", "અગાઉ", "હતું", "હતી", "ગયા", "પાછલા", "પહેલા", "pahela", "agau", "hatu", "pachla"],
        "future": ["પછી", "આગામી", "થશે", "આવનાર", "આવતા", "પછીના", "pachi", "aagami", "thashe", "aavnara"],
    },
    "kn": {
        "past": ["ಹಿಂದೆ", "ಮೊದಲು", "ಕಳೆದ", "ಇತ್ತು", "ಆಗಿತ್ತು", "ಹಿಂದಿನ", "hinde", "modalu", "kaleda", "ittu"],
        "future": ["ಮುಂದಿನ", "ನಂತರ", "ಆಗಲಿದೆ", "ಬರುವ", "ಮುಂದೆ", "mundina", "nantara", "agalide", "baruva"],
    },
    "ml": {
        "past": ["മുമ്പ്", "കഴിഞ്ഞ", "ആയിരുന്നു", "ഉണ്ടായിരുന്നു", "മുമ്പത്തെ", "mumbu", "kazhinja", "aayirunnu"],
        "future": ["അടുത്ത", "ശേഷം", "വരുന്ന", "ഉണ്ടാകും", "ഇനി", "adutha", "shesham", "varunna", "undaakum"],
    },
    "ur": {
        "past": ["پہلے", "گزشتہ", "تھا", "تھی", "تھے", "سابقہ", "پچھلے", "pehle", "guzashta", "tha", "thi", "pichle"],
        "future": ["اگلے", "بعد", "ہوگا", "ہوگی", "آئندہ", "آنے والے", "میں", "agle", "baad", "hoga", "hogi", "aane wale"],
    },
    "pa": {
        "past": ["ਪਹਿਲਾਂ", "ਬੀਤਿਆ", "ਸੀ", "ਪਿਛਲੇ", "ਪਿਛਲਾ", "ਪਹਿਲਾ", "pahila", "si", "pichle", "beeteya"],
        "future": ["ਅਗਲੇ", "ਬਾਅਦ", "ਹੋਵੇਗਾ", "ਹੋਵੇਗੀ", "ਆਉਣ ਵਾਲੇ", "ਅਗਲਾ", "agle", "baad", "hovega", "aaun wale"],
    },
    "or": {
        "past": ["ପୂର୍ବରୁ", "ଅତୀତ", "ଥିଲା", "ଗତ", "ପୂର୍ବେ", "ପୂର୍ବ", "purbartu", "thila", "gata", "purbe"],
        "future": ["ପରେ", "ଆଗାମୀ", "ହେବ", "ପରବର୍ତ୍ତୀ", "ଆସନ୍ତା", "pare", "aagami", "heba", "parabartti"],
    },
    "as": {
        "past": ["আগতে", "অতীত", "আছিল", "যোৱা", "পূৰ্বৰ", "পূৰ্বে", "agote", "asila", "jowa", "purbe"],
        "future": ["পিছত", "আগন্তুক", "হব", "পৰৱৰ্তী", "অহা", "pisot", "agontuk", "hobo", "poroborti"],
    },
    "ne": {
        "past": ["पहिले", "बितेको", "थियो", "अघि", "विगत", "गएको", "pahile", "thiyo", "aghee", "biteko"],
        "future": ["अर्को", "पछि", "हुनेछ", "आगामी", "आउने", "arko", "pachi", "hunecha", "aune"],
    },
    "sa": {
        "past": ["पूर्वम्", "अतीते", "आसीत्", "पूर्वे", "गत", "भूतपूर्व", "purvam", "asit", "atite"],
        "future": ["अग्रिमे", "अनन्तरम्", "भविष्यति", "परम्", "आगामी", "agrime", "bhavishyati", "anantaram"],
    },
}


# Regional Unit Labels for Past (Recorded) vs Future (Expected)
REGIONAL_TEMPORAL_LABELS: dict[str, dict[str, str]] = {
    "en": {"recorded": "recorded", "expected": "expected"},
    "hi": {"recorded": "दर्ज की गई", "expected": "अपेक्षित"},
    "bn": {"recorded": "রেকর্ড করা হয়েছে", "expected": "প্রত্যাশিত"},
    "ta": {"recorded": "பதிவு செய்யப்பட்டது", "expected": "எதிர்பார்க்கப்படுகிறது"},
    "te": {"recorded": "నమోదైంది", "expected": "ఊహించబడింది"},
    "mr": {"recorded": "नोंदवली गेली", "expected": "अपेक्षित"},
    "gu": {"recorded": "નોંધાયેલ", "expected": "અપેક્ષિત"},
    "kn": {"recorded": "ದಾಖಲಾಗಿದೆ", "expected": "ನಿರೀಕ್ಷಿಸಲಾಗಿದೆ"},
    "ml": {"recorded": "രേഖപ്പെടുത്തി", "expected": "പ്രതീക്ഷിക്കുന്നു"},
    "ur": {"recorded": "درج کی گئی", "expected": "متوقع"},
    "pa": {"recorded": "ਦਰਜ ਕੀਤੀ ਗਈ", "expected": "ਅਨੁਮਾਨਿਤ"},
    "or": {"recorded": "ରେକର୍ଡ ହୋଇଛି", "expected": "ପ୍ରତ୍ୟାଶିତ"},
    "as": {"recorded": "নথিভুক্ত কৰা হৈছে", "expected": "প্ৰত্যাশিত"},
    "ne": {"recorded": "रेकर्ड गरिएको", "expected": "अपेक्षित"},
    "sa": {"recorded": "अभिलेखितम्", "expected": "प्रत्याशितम्"},
}


PAST_TENSE_REGEX = re.compile(
    r"(?:"
    r"\b(?:previous|previously|ago|last|past|prior|earlier|was|were|did|had|recorded)\b|"
    r"\b(?:pehle|pahle|beeta|beete|pichle|pichhla|pichli|tha|thi|thhey)\b|"
    r"पहले|बीता|बीते|पिछले|पिछला|पिछली|था|थी|थे|"
    r"پہلے|گزشتہ|تھا|تھی|"
    r"আগে|পূর্বে|গত|ছিল|"
    r"पूर्वी|मागील|होता|होती|होते|"
    r"પહેલાં|અગાઉ|હતું|હતી|"
    r"முன்பு|முன்னர்|கடந்த|"
    r"క్రితం|ముందు|గత|"
    r"ಹಿಂದೆ|ಮೊದಲು|ಕಳೆದ|"
    r"മുമ്പ്|കഴിഞ്ഞ"
    r")",
    re.IGNORECASE,
)

STRONG_PAST_REGEX = re.compile(
    r"(?:"
    r"\b(?:ago|previous|previously|last|past|prior|earlier|recorded)\b|"
    r"\b(?:pehle|pahle|beeta|beete|pichle|pichhla)\b|"
    r"पहले|बीता|बीते|पिछले|पिछला|پہلے|گزشتہ|আগে|পূর্বে|গত|पूर्वी|मागील|પહેલાં|મુன்பு|క్రితం|ಹಿಂದೆ|മുമ്പ്"
    r")",
    re.IGNORECASE,
)

FUTURE_TENSE_REGEX = re.compile(
    r"(?:"
    r"\b(?:next|in|will|upcoming|within|after|coming)\b|"
    r"\b(?:agle|agla|agli|aane\s+wal[aei]|aage|baad|hoga|hogi|hoge)\b|"
    r"अगले|अगला|अगली|आने\s+वाल[ाेी]|आगे|बाद|होगा|होगी|होगे|"
    r"اگلے|بعد|ہوگا|ہوگی|"
    r"পরবর্তী|পরে|হবে|"
    r"पुढील|नंतर|होईल|"
    r"આગામી|પછી|થશે|"
    r"அடுத்து|பின்|"
    r"తర్వాత|రాబోయే|"
    r"ಮುಂದಿನ|ನಂತರ|"
    r"അടുത്ത|ശേഷം"
    r")",
    re.IGNORECASE,
)


def parse_dynamic_time(query: str, lang_code: Optional[str] = None) -> Optional[int]:
    """
    Universal Polyglot Temporal Resolver across all 15 scheduled languages:
      - Negative integer for past queries (e.g. '30 mins ago' -> -30, '30 minute pehle' -> -30)
      - Positive integer for future queries (e.g. 'in 30 mins' -> +30, 'next 15 mins' -> +15)
      - None if no temporal slot detected.
    
    Supports: en, hi, bn, ta, te, mr, gu, kn, ml, ur, pa, or, as, ne, sa.
    """
    if not query:
        return None

    norm = normalize_indic_digits(query.strip())
    q_low = norm.lower()
    raw_offset = get_query_time_offset(norm)
    if raw_offset is None:
        return None

    norm_lang = (lang_code or "").strip().lower().split("-")[0].split("_")[0] if lang_code else None

    # 1. Language-Specific Matching if lang_code provided
    if norm_lang and norm_lang in TEMPORAL_MARKERS:
        lang_dict = TEMPORAL_MARKERS[norm_lang]
        for past_word in lang_dict["past"]:
            if past_word.lower() in q_low:
                return -abs(raw_offset)
        for fut_word in lang_dict["future"]:
            if fut_word.lower() in q_low:
                return abs(raw_offset)

    # 2. Strong Universal Past Marker Check across all 15 languages
    if STRONG_PAST_REGEX.search(norm):
        return -abs(raw_offset)

    has_past = False
    for l_key, l_dict in TEMPORAL_MARKERS.items():
        for past_word in l_dict["past"]:
            if past_word.isascii():
                if re.search(r"\b" + re.escape(past_word) + r"\b", q_low):
                    has_past = True
                    break
            else:
                if past_word.lower() in q_low:
                    has_past = True
                    break
        if has_past:
            break

    has_future = False
    for l_key, l_dict in TEMPORAL_MARKERS.items():
        for fut_word in l_dict["future"]:
            if fut_word.isascii():
                if re.search(r"\b" + re.escape(fut_word) + r"\b", q_low):
                    has_future = True
                    break
            else:
                if fut_word.lower() in q_low:
                    has_future = True
                    break
        if has_future:
            break

    if has_future and not has_past:
        return abs(raw_offset)

    if has_past and not has_future:
        return -abs(raw_offset)

    regex_past = bool(PAST_TENSE_REGEX.search(norm))
    regex_future = bool(FUTURE_TENSE_REGEX.search(norm))

    if regex_past and not regex_future:
        return -abs(raw_offset)

    # Inquisitive past questions starting with was/were/did
    if re.search(r"^\s*(?:was|were|did|had)\b", norm, re.IGNORECASE):
        return -abs(raw_offset)

    return abs(raw_offset)


def extract_minute_offset(query: str) -> Optional[int]:
    """Alias for get_query_time_offset providing explicit minute extraction for data fusion routing."""
    return get_query_time_offset(query)


# ── Hyperlocal Precipitation Intent Detection ──
PRECIP_QUERY_YESNO = "PRECIP_QUERY_YESNO"
PRECIP_QUERY_DURATION = "PRECIP_QUERY_DURATION"


def detect_precip_intent(query: str) -> Optional[str]:
    """
    Detects whether the query is:
    - PRECIP_QUERY_DURATION: Asking when precipitation starts or stops (e.g., 'When will it stop?', 'baarish kab rukegi?').
    - PRECIP_QUERY_YESNO: Asking whether it is currently raining or dry (e.g., 'Is it raining?', 'is it raining outside?').
    """
    if not query:
        return None
    q = query.strip().lower()

    # If the user is explicitly asking about tomorrow or past days, let daily/historical engines handle it
    if any(tw in q for tw in ["tomorrow", "yesterday", "last week", "next week", "kal subah", "kal shaam", "beeta kal", "আগামীকাল", "গতকাল"]):
        return None


    # Duration / Stop / Start patterns
    duration_keywords = [
        "when will it stop", "when will rain stop", "when does it stop", "when will the rain stop",
        "when is rain stopping", "when will it cease", "how long will it rain", "how long will rain continue",
        "when will it start", "when will rain start", "when does rain start", "when will the rain start",
        "when is rain starting", "baarish kab rukegi", "barish kab rukegi", "barish kab band hogi",
        "kab barish band hogi", "barish kab rukhegi", "barish kab khatam hogi", "barish kab shuru hogi",
        "kab barish shuru hogi", "barish kab aayegi", "kab barish hogi", "kab baarish hogi",
        "barish kab tak chalegi", "barish kab tak hogi", "বৃষ্টি কখন থামবে", "বৃষ্টি কখন শুরু হবে",
        "மழை எப்போது நிற்கும்", "மழை எப்போது தொடங்கும்", "వర్షం ఎప్పుడు ఆగుతుంది", "వర్షం ఎప్పుడు మొదలవుతుంది"
    ]
    if any(dk in q for dk in duration_keywords) or re.search(r"\bwhen\s+(?:will|does|is)\s+(?:it|the\s+rain|rain)\s+(?:stop|start|end|clear)\b", q):
        return PRECIP_QUERY_DURATION

    # Yes/No Rain queries
    yesno_keywords = [
        "is it raining", "is it raining now", "is it raining outside", "is it raining here",
        "is it raining there", "is it raining in your area", "is it currently raining",
        "is rain falling", "will it rain", "will it rain now", "will it rain today",
        "is it wet outside", "is there rain", "any rain right now",
        "barish ho rahi hai", "baarish ho rahi hai", "kya barish ho rahi hai", "kya baarish ho rahi hai",
        "barish ho rahi h", "barish pad rahi hai", "kya barish hogi", "barish hogi kya",
        "kya baarish hogi", "baarish hogi kya", "বৃষ্টি কি হচ্ছে", "বৃষ্টি পড়ছে কি",
        "மழை பெய்கிறதா", "மழை வருகிறதா", "వర్షం పడుతోందా"
    ]
    if any(yk in q for yk in yesno_keywords) or re.search(r"\bis\s+it\s+(?:currently\s+)?raining\b", q):
        return PRECIP_QUERY_YESNO

    return None


# Re-export WeatherGPTBrain for convenience and interoperability
def __getattr__(name: str):
    if name == "WeatherGPTBrain":
        from backend.services.rag.service import WeatherGPTBrain
        return WeatherGPTBrain
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


