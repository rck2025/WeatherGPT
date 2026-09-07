import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import os
from pathlib import Path
import sys

# Set standard output encoding to utf-8 if possible
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class GlobalClimateHunter:
    def __init__(self, registry_path=None):
        if registry_path is None:
            # Auto-resolve path relative to the file location to make it robust
            base_dir = Path(__file__).resolve().parents[2]
            registry_path = base_dir / "data" / "source_registry.json"
        
        with open(registry_path, 'r') as f:
            self.registry = json.load(f)
        self.headers = {"User-Agent": "WeatherGPT-SIH-Bot/1.0"}
        # Defaults to the local API for development. Set INGEST_API_URL to the
        # deployed /api/v1/ingest/batch URL when this runs as a cloud cron job.
        self.ingest_url = os.getenv(
            "INGEST_API_URL", "http://127.0.0.1:8000/api/v1/ingest/batch"
        ).strip()
        self.ingest_token = os.getenv("INGEST_API_TOKEN", "").strip()

    def hunt_for_pdfs(self):
        all_discovered_links = []
        
        # Combine all categories dynamically for the hunt
        target_urls = []
        for category, urls in self.registry.items():
            target_urls.extend(urls)
        
        for url in target_urls:
            print(f"[HUNT] Scanning: {url}")
            try:
                res = requests.get(url, headers=self.headers, timeout=10)
                res.raise_for_status()
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Logic: Find every PDF link on the page
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if href.lower().endswith('.pdf'):
                        full_link = urljoin(url, href)
                        all_discovered_links.append(full_link)
            except Exception as e:
                print(f"[WARN] Failed to scan {url}: {e}")

        return list(set(all_discovered_links)) # Remove duplicates

    def trigger_batch_ingest(self, pdf_list):
        if not pdf_list:
            print("[INFO] No PDFs found to ingest.")
            return
        print(f"[START] Found {len(pdf_list)} new bulletins. Sending to ingestion API...")
        
        if not self.ingest_url:
            print("[ERROR] INGEST_API_URL is not configured.")
            return

        # Keep cloud-job concurrency modest to avoid overloading or being
        # rate-limited by official bulletin hosts.
        payload = {"sources": pdf_list, "max_workers": 3}
        headers = {"Content-Type": "application/json"}
        if self.ingest_token:
            headers["X-Ingest-Token"] = self.ingest_token
        
        try:
            res = requests.post(
                self.ingest_url, json=payload, headers=headers, timeout=180
            )
            res.raise_for_status()
            summary = res.json()
            print(
                "[SUCCESS] Ingestion complete: "
                f"{summary.get('ingested_count', 0)}/"
                f"{summary.get('total_sources', len(pdf_list))} sources accepted."
            )
        except Exception as e:
            print(f"[ERROR] Handover failed: {e}")

if __name__ == "__main__":
    hunter = GlobalClimateHunter()
    new_pdfs = hunter.hunt_for_pdfs()
    hunter.trigger_batch_ingest(new_pdfs)
