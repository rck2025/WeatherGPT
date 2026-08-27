import requests
import logging
from typing import Optional
from backend.schemas import Location, LocationInput

# Setup basic logging for debugging failures
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LocationResolver:
    def __init__(self):
        self.headers = {"User-Agent": "WeatherGPT_SIH_Project_Contact@team.com"}
        self.nominatim_url = "https://nominatim.openstreetmap.org"

    def resolve(self, loc_in: Optional[LocationInput]) -> Optional[Location]:
        """
        Refined Resolution Logic:
        Returns a valid Location object or None if resolution fails completely.
        """
        # --- 1. REVERSE GEOCODING (GPS Check) ---
        if loc_in and self._is_valid_gps(loc_in.latitude, loc_in.longitude):
            res = self._reverse_geocode(loc_in.latitude, loc_in.longitude)
            if res: return res

        # --- 2. FORWARD GEOCODING (Search Check) ---
        search_query = self._extract_query(loc_in)
        if search_query:
            # Enforce Indian context to avoid global name collisions
            res = self._forward_geocode(f"{search_query}, India")
            if res: return res

        # --- 3. IP LOOKUP (Final Effort) ---
        return self._ip_fallback()

    def _is_valid_gps(self, lat: Optional[float], lon: Optional[float]) -> bool:
        """Validates that coordinates are within realistic bounds."""
        if lat is None or lon is None: return False
        return -90 <= lat <= 90 and -180 <= lon <= 180

    def _extract_query(self, loc_in: Optional[LocationInput]) -> Optional[str]:
        if not loc_in: return None

        parts = [
            loc_in.city,
            loc_in.district,
            loc_in.state,
            loc_in.country,
        ]

        return ", ".join(
            part.strip()
            for part in parts
            if part and part.strip()
        ) or loc_in.raw_text

    def _forward_geocode(self, query: str) -> Optional[Location]:
        try:
            params = {"q": query, "format": "json", "limit": 1, "addressdetails": 1}
            response = requests.get(f"{self.nominatim_url}/search", params=params, headers=self.headers, timeout=5)
            response.raise_for_status()
            res = response.json()

            if res:
                data = res[0]
                addr = data.get('address', {})
                return Location(
                    latitude=float(data['lat']),
                    longitude=float(data['lon']),
                    city=addr.get('city') or addr.get('town') or addr.get('village') or query.split(',')[0],
                    state=addr.get('state'),
                    country="India",
                    timezone="Asia/Kolkata"
                )
        except Exception as e:
            logger.error(f"Forward geocode failed: {e}")
        return None

    def _reverse_geocode(self, lat: float, lon: float) -> Optional[Location]:
        try:
            params = {"lat": lat, "lon": lon, "format": "json"}
            response = requests.get(f"{self.nominatim_url}/reverse", params=params, headers=self.headers, timeout=5)
            response.raise_for_status()
            res = response.json()

            if res:
                addr = res.get('address', {})
                return Location(
                    latitude=lat,
                    longitude=lon,
                    city=addr.get('city') or addr.get('town') or addr.get('village'),
                    state=addr.get('state'),
                    country="India",
                    timezone="Asia/Kolkata"
                )
        except Exception as e:
            logger.error(f"Reverse geocode failed: {e}")
        return None

    def _ip_fallback(self) -> Optional[Location]:
        """Last resort IP check. Returns None if connectivity or API fails."""
        try:
            response = requests.get("http://ip-api.com/json/", timeout=5)
            response.raise_for_status()
            res = response.json()
            if res.get('status') == 'success' and res.get('country') == 'India':
                return Location(
                    latitude=res['lat'],
                    longitude=res['lon'],
                    city=res['city'],
                    state=res['regionName'],
                    country="India",
                    timezone="Asia/Kolkata"
                )
        except Exception as e:
            logger.error(f"IP Fallback failed: {e}")
        return None


# Instance for Teammate 1
location_resolver = LocationResolver()