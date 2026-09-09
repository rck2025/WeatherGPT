"""
Tests for Dynamic Nowcasting & Temporal Slot Filling across 15 Indian Languages.
Verifies:
1. get_query_time_offset across multiple scripts and Indic numerals.
2. Minutely15Forecast schema parsing and WeatherResponse integration.
3. detect_temporal_intent correctly classifying nowcast queries.
4. RAG Service Nowcast Specialist deterministic reasoning and NWP citation.
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.schemas import (
    Location,
    WeatherResponse,
    CurrentWeatherData,
    Minutely15Forecast,
    ChatRequest,
)
from backend.services.rag.brain import (
    get_query_time_offset,
    normalize_indic_digits,
)
from backend.services.rag.service import (
    detect_temporal_intent,
    WeatherGPTBrain,
)


# ------------------------------------------------------------------
# 1. NUMERAL NORMALIZATION ACROSS INDIC SCRIPTS
# ------------------------------------------------------------------
def test_normalize_indic_digits():
    assert normalize_indic_digits("१५") == "15"  # Devanagari
    assert normalize_indic_digits("১৫") == "15"  # Bengali
    assert normalize_indic_digits("੧੫") == "15"  # Gurmukhi
    assert normalize_indic_digits("૧૫") == "15"  # Gujarati
    assert normalize_indic_digits("୧୫") == "15"  # Odia
    assert normalize_indic_digits("௧௫") == "15"  # Tamil
    assert normalize_indic_digits("౧౫") == "15"  # Telugu
    assert normalize_indic_digits("೧೫") == "15"  # Kannada
    assert normalize_indic_digits("൧൫") == "15"  # Malayalam
    assert normalize_indic_digits("۱۵") == "15"  # Urdu/Perso-Arabic


# ------------------------------------------------------------------
# 2. MULTILINGUAL TEMPORAL SLOT EXTRACTION
# ------------------------------------------------------------------
def test_temporal_slot_english():
    assert get_query_time_offset("Will it rain in the next 15 mins?") == 15
    assert get_query_time_offset("Will it rain in the next 30 minutes in Mumbai?") == 30
    assert get_query_time_offset("Is there a thunderstorm in 2 hours?") == 120
    assert get_query_time_offset("Will it rain within half an hour?") == 30
    assert get_query_time_offset("Any rain in an hour?") == 60
    assert get_query_time_offset("Will it rain tomorrow in Kolkata?") == 1440
    assert get_query_time_offset("How is the weather today?") is None


def test_temporal_slot_indic_languages():
    # Hindi (Romanized & Devanagari)
    assert get_query_time_offset("Kya agle 15 minute mein baarish hogi?") == 15
    assert get_query_time_offset("क्या अगले ३० मिनट में बारिश होगी?") == 30
    assert get_query_time_offset("अगले २ घंटे में कैसा मौसम रहेगा?") == 120
    assert get_query_time_offset("आधा घंटा में बारिश होगी क्या?") == 30

    # Bengali / Assamese
    assert get_query_time_offset("কলকাতা তে পরবর্তী ১৫ মিনিট এ বৃষ্টি হবে কি?") == 15
    assert get_query_time_offset("পরবর্তী ১ ঘণ্টা আবহাওয়া কেমন?") == 60
    assert get_query_time_offset("আধা ঘণ্টা তে বৃষ্টি আসবে?") == 30

    # Marathi
    assert get_query_time_offset("पुढील १५ मिनिटे पाऊस पडेल का?") == 15
    assert get_query_time_offset("पुढील २ तास पाऊस होईल का?") == 120
    assert get_query_time_offset("अर्धा तास हवामान कसे असेल?") == 30

    # Gujarati
    assert get_query_time_offset("આગામી ૧૫ મિનિટ માં વરસાદ પડશે?") == 15
    assert get_query_time_offset("૨ કલાક પછી શું થશે?") == 120

    # Tamil
    assert get_query_time_offset("அடுத்த 15 நிமிடங்கள் மழை பெய்யுமா?") == 15
    assert get_query_time_offset("அரை மணி நேரத்தில் மழை வருமா?") == 30

    # Telugu
    assert get_query_time_offset("తదుపరి 15 నిమిషాలు వర్షం పడుతుందా?") == 15
    assert get_query_time_offset("2 గంటల్లో వాతావరణం ఎలా ఉంటుంది?") == 120

    # Urdu
    assert get_query_time_offset("کیا اگلے ۱۵ منٹ میں بارش ہوگی؟") == 15
    assert get_query_time_offset("اگلے ۲ گھنٹے میں موسم کیسا رہے گا؟") == 120


# ------------------------------------------------------------------
# 3. INTENT DETECTION: NOWCAST VS FORECAST VS PAST
# ------------------------------------------------------------------
def test_detect_temporal_intent_nowcast():
    assert detect_temporal_intent("Will it rain in the next 15 mins?") == "nowcast"
    assert detect_temporal_intent("Kya agle 15 minute mein baarish hogi?") == "nowcast"
    assert detect_temporal_intent("क्या अगले ३० मिनट में बारिश होगी?") == "nowcast"
    assert detect_temporal_intent("Give me a 3-hour nowcast for Kolkata") == "nowcast"

    # Future
    assert detect_temporal_intent("Will it rain tomorrow in Delhi?") == "future"
    assert detect_temporal_intent("Kal mausam kaisa hoga?") == "future"

    # Past
    assert detect_temporal_intent("What was the weather yesterday?") == "past"
    assert detect_temporal_intent("Cyclone Amphan May 20 2020 recorded rainfall") == "past"


# ------------------------------------------------------------------
# 4. SCHEMA INTEGRATION: MINUTELY-15 NWP DATA
# ------------------------------------------------------------------
def test_minutely_15_schema():
    now = datetime.now()
    intervals = [
        Minutely15Forecast(
            timestamp=now + timedelta(minutes=15),
            precipitation=0.0,
            weather_code=0,
            rain=0.0,
        ),
        Minutely15Forecast(
            timestamp=now + timedelta(minutes=30),
            precipitation=3.2,
            weather_code=61,
            rain=3.2,
        ),
    ]
    resp = WeatherResponse(
        current=CurrentWeatherData(temperature=28.5, precipitation=0.0),
        minutely_15=intervals,
    )
    assert len(resp.minutely_15) == 2
    assert resp.minutely_15[0].precipitation == 0.0
    assert resp.minutely_15[1].precipitation == 3.2


# ------------------------------------------------------------------
# 5. NOWCAST SPECIALIST REASONING & NWP CITATION
# ------------------------------------------------------------------
def test_nowcast_specialist_rain_prediction():
    brain = WeatherGPTBrain()
    now = datetime.now()

    # Rain predicted at +30 min (3.5mm)
    intervals = [
        Minutely15Forecast(timestamp=now + timedelta(minutes=15), precipitation=0.0, weather_code=0, rain=0.0),
        Minutely15Forecast(timestamp=now + timedelta(minutes=30), precipitation=3.5, weather_code=61, rain=3.5),
        Minutely15Forecast(timestamp=now + timedelta(minutes=45), precipitation=4.0, weather_code=63, rain=4.0),
    ]
    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=29.0, humidity=85, wind_speed=15.0, precipitation=0.0),
        minutely_15=intervals,
    )
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")
    req = ChatRequest(query="Will it rain in the next 45 minutes in Kolkata?")

    resp = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[])
    reply = resp["bot_reply"]

    # Must confirm rain start in ~30 mins and cite NWP Minutely Model
    assert "approximately 30 minutes" in reply or "30" in reply
    assert "NWP High-Resolution Minutely Model" in reply
    assert any("NWP" in s["source"] for s in resp["sources"])


def test_nowcast_specialist_no_rain_prediction():
    brain = WeatherGPTBrain()
    now = datetime.now()

    # Dry across all intervals
    intervals = [
        Minutely15Forecast(timestamp=now + timedelta(minutes=15), precipitation=0.0, weather_code=0, rain=0.0),
        Minutely15Forecast(timestamp=now + timedelta(minutes=30), precipitation=0.0, weather_code=0, rain=0.0),
    ]
    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=31.0, humidity=60, wind_speed=10.0, precipitation=0.0),
        minutely_15=intervals,
    )
    loc = Location(latitude=19.0760, longitude=72.8777, city="Mumbai")
    req = ChatRequest(query="Will it rain in the next 15 minutes in Mumbai?")

    resp = brain.query_with_schemas(request=req, weather_data=weather, location=loc, alerts=[])
    reply = resp["bot_reply"]

    # Must indicate no precipitation in next 15 minutes and cite NWP
    assert "No precipitation" in reply or "0.0" in reply
    assert "NWP High-Resolution Minutely Model" in reply
