import logging
import os
import re
from typing import List, Optional

from backend.schemas import WeatherAlert

logger = logging.getLogger(__name__)

# Comprehensive list of Indian States, Union Territories, and Major Cities/Districts
INDIAN_LOCATIONS = [
    # States & Union Territories
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Orissa", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Jammu & Kashmir", "Ladakh", "Puducherry",
    "Chandigarh", "Andaman and Nicobar", "Lakshadweep", "Dadra and Nagar Haveli",
    "Daman and Diu",
    # Major Cities & Regions
    "Mumbai", "Bengaluru", "Bangalore", "Hyderabad", "Chennai", "Kolkata",
    "Ahmedabad", "Pune", "Surat", "Jaipur", "Lucknow", "Kanpur", "Nagpur",
    "Indore", "Thane", "Bhopal", "Visakhapatnam", "Vizag", "Patna", "Vadodara",
    "Ghaziabad", "Ludhiana", "Agra", "Nashik", "Faridabad", "Meerut", "Rajkot",
    "Varanasi", "Srinagar", "Aurangabad", "Dhanbad", "Amritsar", "Navi Mumbai",
    "Allahabad", "Prayagraj", "Ranchi", "Howrah", "Coimbatore", "Jabalpur",
    "Gwalior", "Vijayawada", "Jodhpur", "Madurai", "Raipur", "Kota", "Guwahati",
    "Solapur", "Hubli", "Dharwad", "Bareilly", "Moradabad", "Mysore", "Mysuru",
    "Gurgaon", "Gurugram", "Noida", "Aligarh", "Jalandhar", "Tiruchirappalli",
    "Bhubaneswar", "Salem", "Warangal", "Jalgaon", "Thiruvananthapuram", "Kochi",
    "Cochin", "Kozhikode", "Calicut", "Kolhapur", "Siliguri", "Cuttack", "Puri",
    "Rourkela", "Dehradun", "Shimla", "Haridwar", "Rishikesh", "Nainital",
    "Gangtok", "Imphal", "Shillong", "Aizawl", "Agartala", "Kohima", "Itanagar",
    "Port Blair", "Udaipur", "Mangalore", "Mangaluru", "Mangalore", "Belgaum",
    "Belagavi", "Kurnool", "Nellore", "Tirupati", "Rajahmundry", "Guntur",
    "Panaji", "Margao", "Rohtak", "Hisar", "Panipat", "Karnal", "Ambala",
    "Dharamshala", "Mandi", "Kullu", "Manali", "Bokaro", "Jamshedpur", "Hazaribagh",
    "Ujjain", "Dewas", "Ratlam", "Satna", "Rewa", "Amravati", "Nanded",
    "Kolhapur", "Akola", "Latur", "Dhule", "Ahmednagar", "Chandrapur",
    "Parbhani", "Jalna", "Bhiwandi", "Malegaon", "Bikaner", "Ajmer", "Bhilwara",
    "Alwar", "Bharatpur", "Sikar", "Pali", "Tirunelveli", "Tiruppur", "Erode",
    "Vellore", "Thoothukudi", "Dindigul", "Thanjavur", "Nizamabad", "Karimnagar",
    "Ramagundam", "Khammam", "Mahbubnagar", "Nalgonda", "Gorakhpur", "Jhansi",
    "Muzaffarnagar", "Mathura", "Ayodhya", "Firozabad", "Saharanpur", "Gaya",
    "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga", "Asansol", "Durgapur",
    "Bardhaman", "Malda", "Kharagpur", "Darjeeling", "Kalimpong", "Sundarbans"
]


class WeatherAlertAdapter:
    """
    Adapter that transforms raw text and metadata into a validated WeatherAlert model.
    """

    EXTREME_KEYWORDS = [
        "red alert",
        "extremely severe",
        "severe cyclonic",
        "severe",
        "catastrophic",
        "flash flood",
        "cloudburst",
        "landslide disaster"
    ]

    HIGH_KEYWORDS = [
        "warning",
        "orange alert",
        "heavy rainfall",
        "high risk",
        "cyclone",
        "flood alert",
        "thunderstorm warning"
    ]

    def __init__(self, locations: Optional[List[str]] = None):
        self.locations = locations or INDIAN_LOCATIONS
        # Compile a single regex for location matching (sorted by length descending to match longest multi-word names first)
        sorted_locs = sorted(self.locations, key=len, reverse=True)
        pattern = r"\b(" + "|".join(re.escape(loc) for loc in sorted_locs) + r")\b"
        self._location_regex = re.compile(pattern, re.IGNORECASE)

    def extract_location(self, text: str) -> Optional[str]:
        """
        Scan text using regex to find Indian city or state names.
        Returns the first matching location name (normalized) or None.
        """
        if not text:
            return None

        match = self._location_regex.search(text)
        if match:
            # Return title-cased location name found
            return match.group(1).title()

        return None

    def extract_title(self, raw_text: str, source: str) -> str:
        """
        Extract the title from the first non-empty line of text or fallback to filename/URL basename.
        """
        lines = [line.strip("#* \t") for line in raw_text.splitlines() if line.strip("#* \t")]
        if lines:
            first_line = lines[0]
            # If the first line is reasonable length, use it
            if len(first_line) <= 120:
                return first_line
            # Truncate if too long
            return first_line[:117] + "..."

        # Fallback to source filename or URL basename
        basename = os.path.basename(source.rstrip("/\\"))
        return basename if basename else "Weather Alert"

    def determine_severity(self, text: str) -> str:
        """
        Map severity:
        - 'Extreme': if keywords like 'red alert' or 'severe' appear.
        - 'High': if keywords like 'warning' appear.
        - 'Moderate': otherwise.
        """
        text_lower = text.lower()

        if any(keyword in text_lower for keyword in self.EXTREME_KEYWORDS):
            return "Extreme"

        if any(keyword in text_lower for keyword in self.HIGH_KEYWORDS):
            return "High"

        return "Moderate"

    def format_description(self, raw_text: str, location: Optional[str]) -> str:
        """
        Prepend location data to the description in brackets, e.g., '[Location: Mumbai] The forecast indicates...'
        """
        loc_str = location if location else "Unspecified"
        prefix = f"[Location: {loc_str}]"
        
        cleaned_text = raw_text.strip()
        return f"{prefix} {cleaned_text}"

    def adapt(self, raw_text: str, source: str) -> WeatherAlert:
        """
        Map raw text and source into a validated WeatherAlert schema object.
        """
        if not raw_text:
            raw_text = ""

        # 1. Location detection
        location = self.extract_location(raw_text)

        # 2. Title extraction
        title = self.extract_title(raw_text, source)

        # 3. Severity determination
        severity = self.determine_severity(raw_text)

        # 4. Description with prepended [Location: ...]
        description = self.format_description(raw_text, location)

        # 5. Build and validate WeatherAlert
        lat, lon = None, None
        if location:
            from backend.services.rag.service import DISTRICT_CENTROIDS
            lat, lon = DISTRICT_CENTROIDS.get(location.lower(), (None, None))

        alert = WeatherAlert(
            title=title,
            description=description,
            severity=severity,
            source=source,
            latitude=lat,
            longitude=lon,
        )

        return alert

    def to_weather_alert(self, raw_text: str, source: str) -> WeatherAlert:
        """
        Alias for adapt to convert raw text and source into a WeatherAlert object.
        """
        return self.adapt(raw_text, source)
