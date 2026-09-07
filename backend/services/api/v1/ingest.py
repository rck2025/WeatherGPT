import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import secrets
import threading
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.schemas import WeatherAlert
from backend.services.ingestion.adapter import WeatherAlertAdapter
from backend.services.ingestion.scraper import UniversalScraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])

scraper = UniversalScraper()
adapter = WeatherAlertAdapter()
_alerts_lock = threading.Lock()


class IngestBatchRequest(BaseModel):
    sources: List[str] = Field(
        ...,
        description="List of file paths or URLs to scrape and ingest concurrently",
        examples=[[
            "https://mausam.imd.gov.in/bulletin.html",
            "backend/data/uploads/cyclone_alert.pdf",
            "backend/data/uploads/flood_bulletin.xlsx"
        ]]
    )
    max_workers: Optional[int] = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of concurrent worker threads for parallel scraping"
    )


class IngestBatchResponse(BaseModel):
    status: str
    total_sources: int
    ingested_count: int
    failed_count: int
    alerts: List[WeatherAlert]


def _process_single_source(source: str) -> Optional[WeatherAlert]:
    """
    Worker task to scrape, filter, and adapt a single source.
    Isolated so individual source failures don't affect other items in batch.
    """
    try:
        raw_text = scraper.extract_text(source)
        if not raw_text:
            logger.info(f"Skipping source '{source}': No content extracted or failed disaster relevance filter.")
            return None

        alert = adapter.adapt(raw_text=raw_text, source=source)
        if alert and isinstance(alert, WeatherAlert):
            return alert

    except Exception as exc:
        logger.error(f"Error processing source '{source}': {exc}", exc_info=False)
        return None

    return None


@router.post("/batch", response_model=IngestBatchResponse)
async def ingest_batch(
    request: IngestBatchRequest,
    x_ingest_token: str | None = Header(default=None),
) -> IngestBatchResponse:
    """
    High-throughput concurrent batch ingestion endpoint.
    
    Execution Flow for each source (processed in parallel):
    1. Scrape raw text (HTML, PDF, DOCX, XLSX, JSON, TXT).
    2. Filter: Discard if not relevant to weather/disaster keywords.
    3. Adapt: Transform into a validated WeatherAlert model with location extraction.
    4. If valid, append the WeatherAlert to the global alerts list in main.py.
    """
    expected_token = os.getenv("INGEST_API_TOKEN", "").strip()
    if expected_token and (
        not x_ingest_token
        or not secrets.compare_digest(x_ingest_token, expected_token)
    ):
        raise HTTPException(status_code=401, detail="Unauthorized ingestion request.")

    import backend.main as main_module

    if not request.sources:
        raise HTTPException(status_code=400, detail="Sources list cannot be empty.")

    loop = asyncio.get_running_loop()
    max_workers = min(request.max_workers or 10, len(request.sources))

    # Run parallel extraction across thread pool
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            loop.run_in_executor(executor, _process_single_source, source)
            for source in request.sources
        ]
        results = await asyncio.gather(*futures, return_exceptions=False)

    ingested_alerts: List[WeatherAlert] = [r for r in results if r is not None]
    failed_count = len(request.sources) - len(ingested_alerts)

    # Thread-safe batch append to global alerts
    with _alerts_lock:
        main_module.alerts.extend(ingested_alerts)

    logger.info(
        f"Batch ingestion complete: {len(ingested_alerts)}/{len(request.sources)} sources ingested."
    )

    return IngestBatchResponse(
        status="success",
        total_sources=len(request.sources),
        ingested_count=len(ingested_alerts),
        failed_count=failed_count,
        alerts=ingested_alerts,
    )
