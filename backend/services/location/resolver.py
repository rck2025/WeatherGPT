import math
import requests
import logging
from typing import Optional, Tuple
from backend.schemas import Location, LocationInput

# district extraction has to be added later

# Setup basic logging for debugging failures
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MAJOR_INDIAN_AIRPORTS = {
    "VECC": {"name": "Kolkata Intl (Netaji Subhash Chandra Bose)", "city": "Kolkata", "lat": 22.65, "lon": 88.45, "state": "West Bengal"},
    "VIDP": {"name": "Delhi Intl (Indira Gandhi)", "city": "Delhi", "lat": 28.56, "lon": 77.10, "state": "Delhi"},
    "VABB": {"name": "Mumbai Intl (Chhatrapati Shivaji Maharaj)", "city": "Mumbai", "lat": 19.09, "lon": 72.87, "state": "Maharashtra"},
    "VOMM": {"name": "Chennai Intl (Meenambakkam)", "city": "Chennai", "lat": 12.99, "lon": 80.17, "state": "Tamil Nadu"},
    "VOBL": {"name": "Bengaluru Intl (Kempegowda)", "city": "Bengaluru", "lat": 13.20, "lon": 77.71, "state": "Karnataka"},
    "VOHS": {"name": "Hyderabad Intl (Rajiv Gandhi)", "city": "Hyderabad", "lat": 17.24, "lon": 78.43, "state": "Telangana"},
    "VAAH": {"name": "Ahmedabad Intl (Sardar Vallabhbhai Patel)", "city": "Ahmedabad", "lat": 23.07, "lon": 72.63, "state": "Gujarat"},
    "VEBS": {"name": "Bhubaneswar (Biju Patnaik)", "city": "Bhubaneswar", "lat": 20.24, "lon": 85.82, "state": "Odisha"},
    "VEPT": {"name": "Patna (Jay Prakash Narayan)", "city": "Patna", "lat": 25.59, "lon": 85.09, "state": "Bihar"},
    "VEGT": {"name": "Guwahati (Lokpriya Gopinath Bordoloi)", "city": "Guwahati", "lat": 26.11, "lon": 91.59, "state": "Assam"},
    "VOCI": {"name": "Cochin Intl", "city": "Kochi", "lat": 10.15, "lon": 76.39, "state": "Kerala"},
    "VIAR": {"name": "Amritsar (Sri Guru Ram Dass Jee)", "city": "Amritsar", "lat": 31.71, "lon": 74.80, "state": "Punjab"},
    "VOGO": {"name": "Goa (Dabolim)", "city": "Goa", "lat": 15.38, "lon": 73.83, "state": "Goa"},
    "VILK": {"name": "Lucknow (Chaudhary Charan Singh)", "city": "Lucknow", "lat": 26.76, "lon": 80.88, "state": "Uttar Pradesh"},
    "VIJP": {"name": "Jaipur Intl", "city": "Jaipur", "lat": 26.82, "lon": 75.81, "state": "Rajasthan"},
}

CITY_TO_ICAO = {
    "kolkata": "VECC",
    "calcutta": "VECC",
    "delhi": "VIDP",
    "new delhi": "VIDP",
    "mumbai": "VABB",
    "bombay": "VABB",
    "chennai": "VOMM",
    "madras": "VOMM",
    "bengaluru": "VOBL",
    "bangalore": "VOBL",
    "hyderabad": "VOHS",
    "ahmedabad": "VAAH",
    "bhubaneswar": "VEBS",
    "patna": "VEPT",
    "guwahati": "VEGT",
    "kochi": "VOCI",
    "cochin": "VOCI",
    "amritsar": "VIAR",
    "goa": "VOGO",
    "lucknow": "VILK",
    "jaipur": "VIJP",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r * c


def get_nearest_icao(lat: Optional[float] = None, lon: Optional[float] = None, city: Optional[str] = None) -> Tuple[str, str]:
    """
    Geospatial Aerodrome Code Resolver.
    Returns (icao_code, airport_name).
    Prioritizes direct city lookup, then geospatial proximity (haversine).
    """
    if city:
        c_clean = str(city).strip().lower()
        for k, icao in CITY_TO_ICAO.items():
            if k in c_clean:
                info = MAJOR_INDIAN_AIRPORTS[icao]
                return icao, info["name"]

    if lat is not None and lon is not None:
        best_icao = "VECC"
        best_dist = float("inf")
        for icao, info in MAJOR_INDIAN_AIRPORTS.items():
            d = _haversine_km(lat, lon, info["lat"], info["lon"])
            if d < best_dist:
                best_dist = d
                best_icao = icao
        return best_icao, MAJOR_INDIAN_AIRPORTS[best_icao]["name"]

    return "VECC", MAJOR_INDIAN_AIRPORTS["VECC"]["name"]


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
            if res:
                return res

            # Coordinates are already enough for Open-Meteo and geospatial
            # rendering. Nominatim is only used to enrich them with a city
            # label, so a timeout/rate-limit must never make location lookup
            # fatal or force an unrelated IP-based fallback.
            resolved_city = loc_in.city or loc_in.district
            icao, ap_name = get_nearest_icao(loc_in.latitude, loc_in.longitude, resolved_city)
            return Location(
                latitude=loc_in.latitude,
                longitude=loc_in.longitude,
                city=resolved_city,
                state=loc_in.state,
                country=loc_in.country or "India",
                timezone="Asia/Kolkata",
                icao_code=icao,
                airport_name=ap_name,
            )

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
                lat = float(data['lat'])
                lon = float(data['lon'])
                city = addr.get('city') or addr.get('town') or addr.get('village') or query.split(',')[0]
                icao, ap_name = get_nearest_icao(lat, lon, city)
                return Location(
                    latitude=lat,
                    longitude=lon,
                    city=city,
                    state=addr.get('state'),
                    country="India",
                    timezone="Asia/Kolkata",
                    icao_code=icao,
                    airport_name=ap_name,
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
                city = addr.get('city') or addr.get('town') or addr.get('village')
                icao, ap_name = get_nearest_icao(lat, lon, city)
                return Location(
                    latitude=lat,
                    longitude=lon,
                    city=city,
                    state=addr.get('state'),
                    country="India",
                    timezone="Asia/Kolkata",
                    icao_code=icao,
                    airport_name=ap_name,
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
                lat = float(res['lat'])
                lon = float(res['lon'])
                city = res['city']
                icao, ap_name = get_nearest_icao(lat, lon, city)
                return Location(
                    latitude=lat,
                    longitude=lon,
                    city=city,
                    state=res['regionName'],
                    country="India",
                    timezone="Asia/Kolkata",
                    icao_code=icao,
                    airport_name=ap_name,
                )
        except Exception as e:
            logger.error(f"IP Fallback failed: {e}")
        return None


# Instance for Teammate 1
location_resolver = LocationResolver()
