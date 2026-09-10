"""
Aviation Risk Engine based on ICAO Annex 3 & DGCA Civil Aviation Requirements (CAR).
Classifies aerodrome telemetry into decision-support flight categories:
VFR (Visual Flight Rules), MVFR (Marginal VFR), and IFR (Instrument Flight Rules / Low Visibility Procedures).
"""
from typing import Any, Dict, Tuple


def classify_flight_rules(decoded_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Decision Support based on ICAO Annex 3 / DGCA CAR.
    Returns:
        (category_badge, advisory_text)
    """
    if not isinstance(decoded_data, dict) or "error" in decoded_data:
        return "🟡 MVFR (MARGINAL)", "Caution: Incomplete aerodrome telemetry. Exercise caution."

    vis = decoded_data.get("visibility_m", 9999)
    wind = decoded_data.get("wind_speed_kts", 0)
    has_convective = decoded_data.get("convective_hazard", False)
    wind_shear = decoded_data.get("wind_shear", False)

    # ICAO/DGCA THRESHOLDS
    if vis < 1500 or wind > 35 or wind_shear:
        advisory = "Critical: Conditions below VFR minimums."
        if wind_shear:
            advisory += " Wind shear warning active on runway approach."
        elif vis < 1500:
            advisory += " Low Visibility Procedures (LVP) in force."
        return "🔴 IFR ONLY (LVP ACTIVE)", advisory
    elif vis < 5000 or has_convective:
        return "🟡 MVFR (MARGINAL)", "Caution: Reduced visibility. Maintain tactical awareness."
    else:
        return "🟢 VFR (SUITABLE)", "Standard visual flight rules apply."
