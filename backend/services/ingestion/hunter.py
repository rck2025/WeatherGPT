import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
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
        print(f"[START] Found {len(pdf_list)} new bulletins. Sending to RAG Brain...")
        
        # This calls YOUR verified ingestion API
        ingest_url = "http://127.0.0.1:8000/api/v1/ingest/batch"
        payload = {"sources": pdf_list}
        
        try:
            res = requests.post(ingest_url, json=payload)
            res.raise_for_status()
            print("[SUCCESS] RAG Synchronized with the latest hunt results.")
        except Exception as e:
            print(f"[ERROR] Handover failed: {e}")

if __name__ == "__main__":
    hunter = GlobalClimateHunter()
    new_pdfs = hunter.hunt_for_pdfs()
    hunter.trigger_batch_ingest(new_pdfs)
