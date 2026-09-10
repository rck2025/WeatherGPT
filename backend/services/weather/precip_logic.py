"""Hyperlocal Precipitation Timing Engine: Scans minutely/hourly data arrays to pinpoint start/stop times."""

from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple


def analyze_precip_timing(
    precip_array: List[float],
    time_array: Optional[List[Any]] = None,
    threshold: float = 0.1,
) -> Tuple[str, int]:
    """
    Scans the precipitation forecast to find start/stop times.
    precip_array: List of mm values (hourly or minutely)
    """
    now = datetime.now(timezone.utc)
    current_precip = float(precip_array[0]) if (precip_array and precip_array[0] is not None) else 0.0

    # Is it raining now?
    is_raining = current_precip > threshold

    event_time = None
    minutes_from_now = 0

    if is_raining:
        # Find when it STOPS
        for i, val in enumerate(precip_array):
            v = float(val) if val is not None else 0.0
            if v <= threshold:
                event_time = time_array[i] if time_array and i < len(time_array) else None
                minutes_from_now = i * 15  # Assuming 15-min intervals
                return "STOPPING", minutes_from_now
    else:
        # Find when it STARTS
        for i, val in enumerate(precip_array):
            v = float(val) if val is not None else 0.0
            if v > threshold:
                event_time = time_array[i] if time_array and i < len(time_array) else None
                minutes_from_now = i * 15
                return "STARTING", minutes_from_now

    return "STABLE", 0

