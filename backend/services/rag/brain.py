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

    # ── 1. Relative Keywords: 'yesterday', 'day before yesterday' ──
    if "day before yesterday" in q_lower or "day before" in q_lower:
        return (ref_date - timedelta(days=2)).strftime("%Y-%m-%d")
    if "yesterday" in q_lower or "beeta kal" in q_lower or "pichle kal" in q_lower or "kal kitni" in q_lower:
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


# Re-export WeatherGPTBrain for convenience and interoperability
def __getattr__(name: str):
    if name == "WeatherGPTBrain":
        from backend.services.rag.service import WeatherGPTBrain
        return WeatherGPTBrain
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
