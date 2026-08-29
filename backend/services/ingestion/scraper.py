import json
import logging
import os
import re
from typing import Any, List, Optional
from urllib.parse import urlparse

# Optional top-level imports with graceful fallback flags
try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import docx
except ImportError:
    docx = None

try:
    import pandas as pd
except ImportError:
    pd = None

logger = logging.getLogger(__name__)


class UniversalScraper:
    """
    Universal text extraction and scraping service supporting:
    - HTML / Web URLs (requests + BeautifulSoup)
    - PDF documents (PyMuPDF / fitz)
    - Word documents (.docx via python-docx)
    - Excel spreadsheets (.xlsx, .xls via pandas & openpyxl)
    - JSON files/payloads (flattened to readable text)
    - Plain text (.txt, .csv, .log)
    
    Includes a disaster relevance filter to filter non-relevant content.
    """

    DISASTER_KEYWORDS = [
        "cyclone",
        "flood",
        "flooding",
        "thunderstorm",
        "drought",
        "heatwave",
        "heavy rainfall",
        "alert",
        "forest fire",
        "earthquake",
        "warning",
        "imd",
        "storm",
        "weather",
        "monsoon",
        "landslide",
        "agromet",
        "crop",
        "farmer",
        "agriculture",
        "wave",
        "ocean",
        "sea", 
        "state",
        "bulletin", 
        "forecast",
        "advisory", 
        # --- ADD THESE TO YOUR EXISTING LIST ---
        
        # 1. General Meteorology & Forecasting
        "forecast", "outlook", "observation", "rainfall", "temperature", 
        "humidity", "satellite", "radar", "climatology", "monsoon", 
        "depression", "low pressure", "western disturbance", "precipitation",

        # 2. Specific Indian Hazards
        "tsunami", "storm surge", "cloudburst", "lightning", "avalanche", 
        "hailstorm", "cold wave", "gale", "squall", "dust storm", 
        "thunderstorm", "lightning",

        # 3. Agricultural Agromet (For Farmers)
        "agromet", "gkms", "crop", "sowing", "harvest", "irrigation", 
        "pest", "livestock", "soil moisture", "advisory", "kharif", "rabi",

        # 4. Marine & Ocean (For Coastal Areas)
        "ocean", "marine", "swell", "tide", "current", "sea state", 
        "significant wave height", "beach", "coastal", "fisherman", "incois",

        # 5. Official Government Reporting
        "press release", "bulletin", "circular", "sop", "guidelines", 
        "situation report", "ministry", "department", "regional", "center", 
        "rmc", "state-wise", "district-wise",

        # 6. Critical Hindi Terms (for regional matching)
        "mausam", "varsha", "chakravat", "chetavani", "suchna", "barish", 
        "toofan", "samachar"
    ]

    def __init__(self, keywords: Optional[List[str]] = None, timeout: int = 15):
        self.keywords = [k.lower() for k in (keywords or self.DISASTER_KEYWORDS)]
        self.timeout = timeout

    def is_relevant(self, text: str, url: str = "") -> bool:
        """
        Grounded Check: Logs the matched keyword for verification.
        """
        if not text or not isinstance(text, str):
            return False

        text_lower = text.lower()
        url_lower = url.lower()

        # 1. AUTO-TRUST: If it's an official IMD or NDMA report, we want it regardless of keywords
        trusted_domains = ["imd.gov.in", "ndma.gov.in", "incois.gov.in"]
        if any(domain in url_lower for domain in trusted_domains):
            logger.info(f"💎 [AUTO-TRUST] Government Source: {url}")
            return True

        # 2. KEYWORD CHECK: See which word matches
        for keyword in self.keywords:
            if keyword in text_lower:
                logger.info(f"🎯 [MATCH] Found keyword '{keyword}' in document.")
                return True

        return False

    def extract_text(self, source_path: str) -> Optional[str]:
        """
        Extract text from the specified source (URL or local file path).
        Applies disaster relevance filter and error handling.
        Returns the extracted text string if relevant, or None if extraction fails or filter fails.
        """
        if not source_path or not isinstance(source_path, str):
            logger.warning("Invalid source_path provided.")
            return None

        raw_text: Optional[str] = None

        try:
            if self._is_url(source_path):
                raw_text = self._extract_from_url(source_path)
            elif os.path.exists(source_path):
                raw_text = self._extract_from_file(source_path)
            else:
                logger.error(f"Source not found or invalid path: {source_path}")
                return None
        except Exception as e:
            logger.error(f"Error extracting text from {source_path}: {e}", exc_info=True)
            return None

        if not raw_text or not raw_text.strip():
            logger.info(f"No text extracted from {source_path}")
            return None

        cleaned_text = self._clean_text(raw_text)

        # Apply disaster relevance filter
        if not self.is_relevant(cleaned_text, source_path):
            logger.info(f"Content from {source_path} did not pass the disaster relevance filter.")
            return None

        return cleaned_text

    def _is_url(self, path: str) -> bool:
        """Check if path is a valid HTTP/HTTPS URL."""
        try:
            parsed = urlparse(path)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def _extract_from_url(self, url: str) -> Optional[str]:
        """Fetch web page and strip HTML tags to extract clean text."""
        if requests is None:
            logger.error("Missing dependency 'requests'. Please install: pip install requests")
            return None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36 WeatherGPT/1.0"
            )
        }
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()

        return self._extract_from_html_string(response.text)

    def _extract_from_file(self, file_path: str) -> Optional[str]:
        """Dispatch file extraction based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".html", ".htm"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return self._extract_from_html_string(f.read())

        elif ext == ".pdf":
            return self._extract_from_pdf(file_path)

        elif ext == ".docx":
            return self._extract_from_docx(file_path)

        elif ext in (".xlsx", ".xls"):
            return self._extract_from_excel(file_path)

        elif ext == ".json":
            return self._extract_from_json(file_path)

        elif ext in (".txt", ".csv", ".log"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        else:
            logger.warning(f"Unrecognized extension '{ext}', attempting plain text read: {file_path}")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    def _extract_from_html_string(self, html_content: str) -> str:
        """Parse HTML string and strip scripts, styles, and markup tags."""
        if BeautifulSoup is not None:
            soup = BeautifulSoup(html_content, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                element.decompose()
            return soup.get_text(separator="\n", strip=True)

        # Fallback regex strip if bs4 is not available
        logger.warning("Missing 'beautifulsoup4'. Falling back to regex HTML stripping.")
        cleaned = re.sub(r"<(script|style).*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        return cleaned

    def _extract_from_pdf(self, file_path: str) -> Optional[str]:
        """Extract text from PDF pages using PyMuPDF (fitz)."""
        if fitz is None:
            logger.error("Missing dependency 'pymupdf'. Please install: pip install pymupdf")
            return None

        doc = None
        try:
            doc = fitz.open(file_path)
            pages_text: List[str] = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text:
                    pages_text.append(text)
            return "\n\n".join(pages_text)
        finally:
            if doc is not None:
                doc.close()

    def _extract_from_docx(self, file_path: str) -> Optional[str]:
        """Extract text from DOCX paragraphs and tables using python-docx."""
        if docx is None:
            logger.error("Missing dependency 'python-docx'. Please install: pip install python-docx")
            return None

        doc = docx.Document(file_path)
        content: List[str] = []

        # Extract text from paragraphs
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                content.append(paragraph.text)

        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    content.append(" | ".join(row_text))

        return "\n".join(content)

    def _extract_from_excel(self, file_path: str) -> Optional[str]:
        """Extract all sheets from an Excel file using pandas."""
        if pd is None:
            logger.error("Missing dependency 'pandas'. Please install: pip install pandas openpyxl")
            return None

        excel_data = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
        content: List[str] = []

        for sheet_name, df in excel_data.items():
            content.append(f"--- Sheet: {sheet_name} ---")
            cleaned_df = df.dropna(how="all").dropna(axis=1, how="all")
            content.append(cleaned_df.to_string(index=False))

        return "\n\n".join(content)

    def _extract_from_json(self, file_path: str) -> Optional[str]:
        """Parse JSON file and flatten into a human-readable text string."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)

        return self._flatten_json_to_string(data)

    def _flatten_json_to_string(self, data: Any, prefix: str = "") -> str:
        """Recursively flatten dicts/lists into structured key: value lines."""
        lines: List[str] = []

        if isinstance(data, dict):
            for key, value in data.items():
                new_key = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(value, (dict, list)):
                    nested = self._flatten_json_to_string(value, new_key)
                    if nested:
                        lines.append(nested)
                else:
                    lines.append(f"{new_key}: {value}")
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                new_key = f"{prefix}[{idx}]"
                if isinstance(item, (dict, list)):
                    nested = self._flatten_json_to_string(item, new_key)
                    if nested:
                        lines.append(nested)
                else:
                    lines.append(f"{new_key}: {item}")
        else:
            lines.append(f"{prefix}: {data}" if prefix else str(data))

        return "\n".join(line for line in lines if line)

    def _clean_text(self, text: str) -> str:
        """Clean carriage returns, excessive whitespace, and normalize line breaks."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
