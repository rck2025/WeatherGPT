"""
Surgical Parser for IMD METAR Strings and Aerodrome Weather Decision Support.
Converts raw METAR strings into structured telemetry objects adhering to ICAO Annex 3.
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional


def decode_metar(metar_string: str) -> Dict[str, Any]:
    """
    Surgical Parser for IMD METAR Strings.
    Converts raw codes into a Decision-Support JSON.
    """
    try:
        if not metar_string or not isinstance(metar_string, str):
            return {"error": "Empty or invalid input", "raw": str(metar_string or "")}

        # Regex to pull core aviation metrics
        wind = re.search(r'(\d{3})(\d{2})G?(\d{2})?KT', metar_string)
        vis = re.search(r'\s(\d{4})\s', metar_string)
        temp_dew = re.search(r'\s(\d{2})/(\d{2})\s', metar_string)
        altimeter = re.search(r'Q(\d{4})', metar_string)

        # Wind shear check
        wind_shear_match = re.search(r'WS\s+(?:ALL\s+RWY|RWY\s*(\w+))', metar_string, re.IGNORECASE)
        wind_shear = bool(wind_shear_match)
        wind_shear_rwy = wind_shear_match.group(1) if (wind_shear_match and wind_shear_match.group(1)) else None

        # Convective clouds (CB / TCU / TS)
        has_convective = bool(re.search(r'\b(CB|TCU|TS|\+TSRA|TSRA|SQ)\b', metar_string, re.IGNORECASE))

        wind_dir = wind.group(1) if wind else "000"
        wind_speed_kts = int(wind.group(2)) if wind else 0
        wind_gust_kts = int(wind.group(3)) if (wind and wind.group(3)) else None
        visibility_m = int(vis.group(1)) if vis else 9999
        temp_c = int(temp_dew.group(1)) if temp_dew else 28
        dewpoint_c = int(temp_dew.group(2)) if temp_dew else 22
        qnh_hpa = int(altimeter.group(1)) if altimeter else 1013

        return {
            "wind_dir": wind_dir,
            "wind_speed_kts": wind_speed_kts,
            "wind_gust_kts": wind_gust_kts,
            "visibility_m": visibility_m,
            "temp_c": temp_c,
            "dewpoint_c": dewpoint_c,
            "qnh_hpa": qnh_hpa,
            "wind_shear": wind_shear,
            "wind_shear_rwy": wind_shear_rwy,
            "convective_hazard": has_convective,
            "raw": metar_string.strip(),
        }
    except Exception:
        return {"error": "Invalid METAR format from IMD source", "raw": metar_string}


def generate_live_metar(
    icao_code: str = "VECC",
    weather_data: Optional[Any] = None,
    wind_shear: bool = False,
    override_vis_m: Optional[int] = None,
) -> str:
    """
    Synthesize or format a live IMD-standard METAR string for a given aerodrome.
    Uses real-time surface observations when available.
    """
    icao = (icao_code or "VECC").strip().upper()
    now = datetime.now(timezone.utc)
    day = now.strftime("%d")
    hour_min = now.strftime("%H%M")
    time_str = f"{day}{hour_min}Z"

    curr = getattr(weather_data, "current", None) if weather_data else None

    # Wind
    wind_spd_kmh = float(getattr(curr, "wind_speed", 15.0) or 15.0) if curr else 15.0
    wind_kts = max(2, int(round(wind_spd_kmh * 0.539957)))
    wind_dir = "020" if icao == "VECC" else ("280" if icao == "VIDP" else "240")

    # Visibility
    if override_vis_m is not None:
        vis_m = int(round(float(override_vis_m)))
    else:
        vis_raw = getattr(curr, "visibility", 6000.0) if curr else 6000.0
        vis_m = int(round(float(vis_raw))) if (vis_raw is not None and float(vis_raw) > 0) else 6000
    vis_m = max(500, min(9999, vis_m))
    vis_str = f"{vis_m:04d}"

    # Temperature and Dewpoint
    temp_c = int(round(getattr(curr, "temperature", 28.0) or 28.0)) if curr else 28
    humidity = float(getattr(curr, "humidity", 70.0) or 70.0) if curr else 70.0
    dew_c = max(0, int(round(temp_c - ((100.0 - humidity) / 5.0))))

    w_code = int(getattr(curr, "weather_code", 0) or 0) if curr else 0
    is_ts = (w_code in (95, 96, 99)) or wind_shear

    # Weather phenomenon & Cloud Layer
    if is_ts:
        phenom = "+TSRA"
        clouds = "FEW015CB BKN025"
        qnh = 1008
    elif vis_m < 2000:
        phenom = "FG"
        clouds = "OVC003"
        qnh = 1012
    elif vis_m < 5000:
        phenom = "HZ"
        clouds = "SCT025"
        qnh = 1012
    else:
        phenom = "NOSIG"
        clouds = "FEW030"
        qnh = 1014

    ws_clause = " WS RWY19L" if (wind_shear or (icao == "VECC" and is_ts)) else ""

    if phenom != "NOSIG":
        return f"METAR {icao} {time_str} {wind_dir}{wind_kts:02d}KT {vis_str} {phenom} {clouds} {temp_c:02d}/{dew_c:02d} Q{qnh}{ws_clause} NOSIG"
    else:
        return f"METAR {icao} {time_str} {wind_dir}{wind_kts:02d}KT {vis_str} {clouds} {temp_c:02d}/{dew_c:02d} Q{qnh}{ws_clause} NOSIG"
