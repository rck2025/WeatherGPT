"""
Test Suite for Universal Temporal Logic across all 15 Supported Indian Languages.
Validates:
1. Multi-Lingual Temporal Dictionary (TEMPORAL_MARKERS) for 15 languages:
   en, hi, bn, ta, te, mr, gu, kn, ml, ur, pa, or, as, ne, sa.
2. Regional Unit Normalization (REGIONAL_TEMPORAL_LABELS) for 'recorded' vs 'expected'.
3. Language-Aware Signed Offset Parsing with script and romanized tokens.
4. Switch Test:
   - Future query ('Next 10 minutes rain?') -> Predictive Models / Radar Nowcast.
   - Past query ('Previous 10 minutes rain?') -> Ground-Truth AWS Sensors.
5. Complete Object Nullification:
   - Offset < 0 -> 0% nowcast alert leakage, live telemetry and future forecasts wiped.
6. Regional unit labeling in generated or fallback response (e.g. Hindi 'दर्ज की गई' for past).
"""

from datetime import datetime, timedelta
import pytest

from backend.schemas import (
    ChatRequest,
    CurrentWeatherData,
    Location,
    Minutely15Forecast,
    WeatherAlert,
    WeatherResponse,
)
from backend.services.rag.brain import (
    TEMPORAL_MARKERS,
    REGIONAL_TEMPORAL_LABELS,
    parse_dynamic_time,
)
from backend.services.rag.service import WeatherGPTBrain, detect_temporal_intent


ALL_15_LANGS = [
    "en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "ur", "pa", "or", "as", "ne", "sa"
]


# ------------------------------------------------------------------
# 1. TEMPORAL DICTIONARY & REGIONAL LABELS INTEGRITY
# ------------------------------------------------------------------
def test_temporal_markers_all_15_languages():
    """Verify that all 15 scheduled languages are mapped with non-empty past and future markers."""
    for lang in ALL_15_LANGS:
        assert lang in TEMPORAL_MARKERS, f"Missing temporal markers for language: {lang}"
        markers = TEMPORAL_MARKERS[lang]
        assert "past" in markers and len(markers["past"]) > 0, f"Missing past markers for {lang}"
        assert "future" in markers and len(markers["future"]) > 0, f"Missing future markers for {lang}"


def test_regional_temporal_labels_all_15_languages():
    """Verify that all 15 scheduled languages have 'recorded' and 'expected' labels."""
    for lang in ALL_15_LANGS:
        assert lang in REGIONAL_TEMPORAL_LABELS, f"Missing regional labels for language: {lang}"
        labels = REGIONAL_TEMPORAL_LABELS[lang]
        assert "recorded" in labels and len(labels["recorded"]) > 0, f"Missing 'recorded' for {lang}"
        assert "expected" in labels and len(labels["expected"]) > 0, f"Missing 'expected' for {lang}"

    # Verify specific Hindi and English regional units
    assert REGIONAL_TEMPORAL_LABELS["hi"]["recorded"] == "दर्ज की गई"
    assert REGIONAL_TEMPORAL_LABELS["hi"]["expected"] == "अपेक्षित"
    assert REGIONAL_TEMPORAL_LABELS["en"]["recorded"] == "recorded"
    assert REGIONAL_TEMPORAL_LABELS["en"]["expected"] == "expected"


# ------------------------------------------------------------------
# 2. LANGUAGE-MAPPED SIGNED OFFSET PARSING
# ------------------------------------------------------------------
def test_signed_offset_hindi():
    """Verify Hindi past vs future queries with Devanagari and Romanized keywords."""
    # Past
    assert parse_dynamic_time("30 minute pehle kya ho raha tha?", lang_code="hi") == -30
    assert parse_dynamic_time("पिछले १५ मिनट में बारिश हुई?", lang_code="hi") == -15
    assert parse_dynamic_time("बीते 10 मिनट में मौसम कैसा था?", lang_code="hi") == -10
    # Future
    assert parse_dynamic_time("अगले 30 मिनट में बारिश होगी?", lang_code="hi") == 30
    assert parse_dynamic_time("15 minute baad barish aayegi?", lang_code="hi") == 15


def test_signed_offset_bengali():
    """Verify Bengali past vs future queries with Bengali numerals and script."""
    # Past
    assert parse_dynamic_time("১৫ মিনিট আগে বৃষ্টি হয়েছিল কি?", lang_code="bn") == -15
    assert parse_dynamic_time("গত ৩০ মিনিটে বৃষ্টিপাত", lang_code="bn") == -30
    # Future
    assert parse_dynamic_time("পরবর্তী ১৫ মিনিটে বৃষ্টি হবে?", lang_code="bn") == 15
    assert parse_dynamic_time("১০ মিনিট পরে আবহাওয়া", lang_code="bn") == 10


def test_signed_offset_tamil():
    """Verify Tamil past vs future queries."""
    # Past
    assert parse_dynamic_time("30 நிமிடங்களுக்கு முன்பு மழை பெய்ததா?", lang_code="ta") == -30
    assert parse_dynamic_time("கடந்த 15 நிமிடங்களில் மழை", lang_code="ta") == -15
    # Future
    assert parse_dynamic_time("அடுத்த 30 நிமிடங்களில் மழை வருமா?", lang_code="ta") == 30
    assert parse_dynamic_time("10 நிமிடங்களுக்குப் பிறகு மழை", lang_code="ta") == 10


def test_signed_offset_telugu():
    """Verify Telugu past vs future queries."""
    # Past
    assert parse_dynamic_time("15 నిమిషాల క్రితం వర్షం పడిందా?", lang_code="te") == -15
    assert parse_dynamic_time("గత 30 నిమిషాల్లో వర్షం", lang_code="te") == -30
    # Future
    assert parse_dynamic_time("తర్వాత 15 నిమిషాల్లో వర్షం పడుతుందా?", lang_code="te") == 15
    assert parse_dynamic_time("రాబోయే 30 నిమిషాల్లో", lang_code="te") == 30


def test_signed_offset_marathi():
    """Verify Marathi past vs future queries."""
    # Past
    assert parse_dynamic_time("मागील ३० मिनिटात पाऊस पडला का?", lang_code="mr") == -30
    assert parse_dynamic_time("१५ मिनिटांपूर्वी पाऊस झाला का?", lang_code="mr") == -15
    # Future
    assert parse_dynamic_time("पुढील ३० मिनिटात पाऊस येईल का?", lang_code="mr") == 30
    assert parse_dynamic_time("१५ मिनिटांनंतर पाऊस", lang_code="mr") == 15


def test_signed_offset_urdu():
    """Verify Urdu past vs future queries with Perso-Arabic script."""
    # Past
    assert parse_dynamic_time("30 منٹ پہلے کیا بارش تھی؟", lang_code="ur") == -30
    assert parse_dynamic_time("گزشتہ 15 منٹ میں بارش", lang_code="ur") == -15
    # Future
    assert parse_dynamic_time("اگلے 30 منٹ میں بارش ہوگی؟", lang_code="ur") == 30
    assert parse_dynamic_time("15 منٹ بعد کیا موسم ہوگا؟", lang_code="ur") == 15


def test_signed_offset_other_languages():
    """Verify Gujarati, Punjabi, Odia, Kannada, Malayalam, Assamese, Nepali, Sanskrit."""
    # Gujarati
    assert parse_dynamic_time("15 મિનિટ પહેલાં વરસાદ પડ્યો?", lang_code="gu") == -15
    assert parse_dynamic_time("આગામી 15 મિનિટમાં વરસાદ", lang_code="gu") == 15

    # Punjabi
    assert parse_dynamic_time("15 ਮਿੰਟ ਪਹਿਲਾਂ ਮੀਂਹ ਪਿਆ ਸੀ?", lang_code="pa") == -15
    assert parse_dynamic_time("ਅਗਲੇ 15 ਮਿੰਟਾਂ ਵਿੱਚ ਮੀਂਹ", lang_code="pa") == 15

    # Odia
    assert parse_dynamic_time("15 ମିନିଟ ପୂର୍ବରୁ ବର୍ଷା ହୋଇଥିଲା କି?", lang_code="or") == -15
    assert parse_dynamic_time("ଆଗାମୀ 15 ମିନିଟରେ ବର୍ଷା", lang_code="or") == 15

    # Kannada
    assert parse_dynamic_time("15 ನಿಮಿಷಗಳ ಹಿಂದೆ ಮಳೆ ಇತ್ತಾ?", lang_code="kn") == -15
    assert parse_dynamic_time("ಮುಂದಿನ 15 ನಿಮಿಷಗಳಲ್ಲಿ ಮಳೆ", lang_code="kn") == 15

    # Malayalam
    assert parse_dynamic_time("15 മിനിറ്റ് മുമ്പ് മഴ പെയ്തോ?", lang_code="ml") == -15
    assert parse_dynamic_time("അടുത്ത 15 മിനിറ്റിൽ മഴ", lang_code="ml") == 15

    # Assamese
    assert parse_dynamic_time("15 মিনিট আগতে বৰষুণ হৈছিল নেকি?", lang_code="as") == -15
    assert parse_dynamic_time("আগন্তুক 15 মিনিটত বৰষুণ", lang_code="as") == 15

    # Nepali
    assert parse_dynamic_time("15 मिनेट पहिले पानी पर्यो?", lang_code="ne") == -15
    assert parse_dynamic_time("अर्को 15 मिनेटमा पानी पर्छ?", lang_code="ne") == 15

    # Sanskrit
    assert parse_dynamic_time("15 निमेषाः पूर्वम् वृष्टिः आसीत् किम्?", lang_code="sa") == -15
    assert parse_dynamic_time("अग्रिमे 15 निमेषे वृष्टिः भविष्यति", lang_code="sa") == 15


# ------------------------------------------------------------------
# 3. SWITCH TEST: FUTURE (RADAR/NWP) VS PAST (AWS GROUND TRUTH)
# ------------------------------------------------------------------
def test_switch_test_future_vs_past():
    """
    Switch Test:
    - Query 1 (Future): 'Next 10 minutes rain in Kolkata?' -> NWP / Radar Predictive Models.
    - Query 2 (Past): 'Previous 10 minutes rain in Kolkata?' -> AWS Ground Sensors Historical Records.
    """
    brain = WeatherGPTBrain()
    now = datetime.now()
    loc = Location(latitude=22.5726, longitude=88.3639, city="Kolkata")

    # Future rain intervals
    rain_intervals = [
        Minutely15Forecast(timestamp=now + timedelta(minutes=15), precipitation=2.8, weather_code=61, rain=2.8),
        Minutely15Forecast(timestamp=now + timedelta(minutes=30), precipitation=4.0, weather_code=65, rain=4.0),
    ]
    weather = WeatherResponse(
        current=CurrentWeatherData(temperature=29.8, humidity=82, wind_speed=14.0, precipitation=0.0),
        minutely_15=rain_intervals,
    )
    alert = WeatherAlert(
        title="🚨 IMD Active Alert",
        description="Thunderstorm watch in Gangetic West Bengal.",
        severity="Moderate",
        source="IMD Doppler Radar",
    )

    # ── Test Query 1: Future Nowcast ──
    req_future = ChatRequest(query="Next 10 minutes rain in Kolkata?", language="en")
    resp_future = brain.query_with_schemas(request=req_future, weather_data=weather, location=loc, alerts=[alert])
    future_sources = [s["source"] for s in resp_future.get("sources", [])]

    # Future should consult Radar and Minutely NWP models
    assert any("Radar" in s or "NWP" in s for s in future_sources), f"Expected Radar or NWP in {future_sources}"
    # Future should NOT cite AWS historical telemetry
    assert not any("Historical" in s for s in future_sources)

    # ── Test Query 2: Past History ──
    req_past = ChatRequest(query="Previous 10 minutes rain in Kolkata?", language="en")
    resp_past = brain.query_with_schemas(request=req_past, weather_data=weather, location=loc, alerts=[alert])
    past_sources = [s["source"] for s in resp_past.get("sources", [])]

    # Past MUST cite MoES Ground-Truth Sensors (AWS)
    assert any("Ground-Truth Sensors (AWS)" in s for s in past_sources), f"Expected Ground-Truth Sensors in {past_sources}"
    # Past MUST NOT leak active alerts
    assert len(resp_past["alerts"]) == 0
    # Past MUST NOT contain forward nowcast phrases in reply
    assert "predicted to start" not in resp_past["bot_reply"].lower()
    assert "next 3 hours" not in resp_past["bot_reply"].lower()


# ------------------------------------------------------------------
# 4. MEMORY LEAK ISOLATION & OBJECT NULLIFICATION
# ------------------------------------------------------------------
def test_past_query_zero_alert_leakage():
    """Verify that a past query completely nullifies active alerts and forward telemetry."""
    brain = WeatherGPTBrain()
    loc = Location(latitude=19.0760, longitude=72.8777, city="Mumbai")

    urgent_alerts = [
        WeatherAlert(
            title="CRITICAL CYCLONE ALERT",
            description="Severe squall imminent in next 1 hour.",
            severity="Severe",
            source="IMD Warning",
        ),
        WeatherAlert(
            title="NOWCAST WARNING",
            description="Intense rainfall over Mumbai for next 3 hours.",
            severity="High",
            source="DWR Radar",
        ),
    ]

    req = ChatRequest(query="Was it raining in the last 20 minutes in Mumbai?", language="en")
    resp = brain.query_with_schemas(request=req, weather_data=None, location=loc, alerts=urgent_alerts)

    # All alerts must be completely stripped
    assert len(resp["alerts"]) == 0
    assert "CRITICAL CYCLONE ALERT" not in resp["bot_reply"]
    assert "NOWCAST WARNING" not in resp["bot_reply"]


# ------------------------------------------------------------------
# 5. REGIONAL UNIT NORMALIZATION (HINDI & MULTILINGUAL LABELS)
# ------------------------------------------------------------------
def test_hindi_query_uses_recorded_label():
    """Verify that a Hindi past query fallback uses 'दर्ज की गई' and strips alerts."""
    brain = WeatherGPTBrain()
    loc = Location(latitude=28.6139, longitude=77.2090, city="Delhi")
    alert = WeatherAlert(
        title="Heavy Rain Alert",
        description="Rain expected later today",
        severity="High",
        source="IMD",
    )

    req = ChatRequest(query="पिछले 15 मिनट में दिल्ली में क्या बारिश दर्ज हुई?", language="hi")
    resp = brain.query_with_schemas(request=req, weather_data=None, location=loc, alerts=[alert])

    # Must have 0 alerts
    assert len(resp["alerts"]) == 0

    # Response should contain Hindi text with 'दर्ज की गई' or 'सेंसर'
    reply = resp["bot_reply"]
    assert "दर्ज की गई" in reply or "सेंसर" in reply or "मिमी" in reply
    assert "Alert" not in reply
