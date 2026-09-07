# 🌦️ WeatherGPT: RAG & Scraper Walkthrough

WeatherGPT is a Retrieval-Augmented Generation (RAG) assistant designed for the Ministry of Earth Sciences (MoES). It combines live weather reports, active alerts, and scraped disaster safety manuals to provide trustworthy disaster-safety answers, complete with agency citations.

---

## 🗺️ System Architecture (USGS + IMD + INCOIS + Bhashini)

The following diagram illustrates how the scraping, multi-hazard ingestion, Bhashini translation bridge, historical time-series engine, and emergency notifier operate:

```mermaid
graph TD
    %% Styling
    classDef ingest fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#01579b;
    classDef query fill:#efebe9,stroke:#5d4037,stroke-width:2px,color:#3e2723;
    classDef storage fill:#efe8e0,stroke:#d84315,stroke-width:2px,color:#bf360c;
    classDef national fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef alert fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c;
    
    subgraph Ingestion Pipeline [Multi-Hazard & Crawler Pipeline]
        registry[source_registry.json] --> hunter[hunter.py: GlobalClimateHunter]
        hunter -- IMD Bulletins --> batch_ingest[ingest.py: /api/v1/ingest/batch]
        batch_ingest --> scraper[scraper.py: UniversalScraper]
        scraper --> adapter[adapter.py: WeatherAlertAdapter]
        
        usgs_feed[USGS Seismic Network] --> hazards[hazards.py: Multi-Hazard Stream]
        incois_feed[INCOIS Ocean Telemetry] --> hazards
        
        hazards --> alert_store[(Unified Live Alert Store)]
        adapter --> alert_store
        
        pdf_dir[backend/data/*.pdf] --> doc_ingest[main.py: /rag/ingest]
        doc_ingest -- RecursiveTextSplitter --> embed[Gemini Embeddings]
        embed --> chroma[(vector_db: ChromaDB)]
    end
    
    subgraph Query Pipeline [RAG, Historical Time-Series & Bhashini Gateway]
        user[User Terminal Query / Voice] --> chat_endpoint[main.py: /chat]
        chat_endpoint --> bhashini_in[translator.py: Bhashini / Indic Gateway]
        bhashini_in -- Normalized Query --> loc[location_resolver]
        
        loc --> weather[open_meteo_service]
        loc --> history[history.py: 1h-7d Historical Engine]
        
        loc & weather & history & alert_store --> rag_service[adapter.py: RAGService]
        rag_service --> chroma_search{Chroma Similarity Search}
        chroma_search -- Top Bulletins --> brain[service.py: WeatherGPTBrain]
        brain -- MoES Authority Mode --> llm[Gemini LLM: gemini-flash-latest]
        
        llm --> bhashini_out[translator.py: Bhashini 15-Language NMT]
        bhashini_out --> tts[service.py: Synchronized Edge-TTS]
        bhashini_out --> response[Structured ChatResponse with history_data]
    end

    subgraph Emergency Disaster Bridge [Low-Bandwidth Out-of-Terminal Notification]
        response -- Critical / Red Alert Trigger --> notifier[notifier.py: send_emergency_whatsapp]
        notifier --> whatsapp[Twilio WhatsApp / SMS Broadcast]
    end

    class registry,hunter,batch_ingest,scraper,adapter,pdf_dir,doc_ingest,embed,usgs_feed,incois_feed,hazards ingest;
    class user,chat_endpoint,loc,weather,history,rag_service,chroma_search,brain,llm,response query;
    class chroma,alert_store storage;
    class bhashini_in,bhashini_out,tts national;
    class notifier,whatsapp alert;
```

---

## 📁 File Structure & Mapping

Here are the key modules and their file locations in the repository:

*   **Ingestion & Scraper Service**:
    *   [`source_registry.json`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/data/source_registry.json): Registry of trusted links/feeds (National IMD, RMCs, Disaster Management, Marine, Agromet).
    *   [`hunter.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/ingestion/hunter.py): Crawls and scans links in the registry to identify and fetch PDF bulletins, then issues batch ingestion calls.
    *   [`scraper.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/ingestion/scraper.py): Universal document text extractor supporting Web URLs, HTML, PDF, Word (DOCX), Excel (XLSX), JSON, and Plain Text.
    *   [`adapter.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/ingestion/adapter.py): Transforms and maps scraped raw text to a structured `WeatherAlert` schema, handling location detection and severity parsing.
    *   [`ingest.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/api/v1/ingest.py): FastAPI batch router that handles concurrent multi-source document ingestion.
*   **RAG Core**:
    *   [`embeddings.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/rag/embeddings.py): Handles GoogleGenerativeAIEmbeddings setup.
    *   [`vector_store.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/rag/vector_store.py): Directs database storage loader and PDF file batch parsing.
    *   [`retriever.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/rag/retriever.py): Executes ChromaDB similarity querying.
    *   [`service.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/rag/service.py): High-level coordinator coordinating vectors retrieval, prompting, and Gemini model generation.
    *   [`adapter.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/rag/adapter.py): Wraps the coordinator to provide a stable schema integration with the API endpoints.
*   **API & Core**:
    *   [`main.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/main.py): FastAPI app entry point exposing endpoints, managing state, and mounting the static frontend.
    *   [`schemas.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/schemas.py): Pydantic specifications for shared data exchange (Weather, Locations, Alerts, RAG documents, ChatRequest, and ChatResponse).

---

## 🕷️ The Scraper Pipeline (`ingestion`)

### 1. Link Hunting (`hunter.py`)
The pipeline begins at [`hunter.py`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/ingestion/hunter.py).
*   **Source Discovery:** Reads [`source_registry.json`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/data/source_registry.json) to retrieve targeted URLs.
*   **PDF Crawling:** Requests each page, parses anchors (`<a>`) using BeautifulSoup, identifies URL endings in `.pdf`, and normalizes them into fully-qualified links.
*   **Handover:** Posts the batch of discovered PDFs to the backend ingestion endpoint. Set `INGEST_API_URL` to the deployed `/api/v1/ingest/batch` URL when running the hunter in the cloud; local development defaults to `http://127.0.0.1:8000/api/v1/ingest/batch`.

### 2. Multi-Format Extraction (`scraper.py`)
The scraper class [`UniversalScraper`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/ingestion/scraper.py) handles extraction from multiple file types:
*   **Web URLs / HTML:** Uses `requests` with a browser User-Agent header, then strips script tags, headers, footers, styles, and SVG markup using `BeautifulSoup` (with regex backfalls if `bs4` is missing).
*   **PDF Documents:** Reads document pages and extracts layout text using PyMuPDF (`fitz`).
*   **Word Documents (`.docx`):** Parses document paragraphs and extracts tables, formatting cells with standard piping (`|`).
*   **Excel Spreadsheets (`.xlsx`, `.xls`):** Iterates over all sheets using `pandas` and `openpyxl`, dropping empty rows/columns, and serializing contents to string tables.
*   **JSON:** Recursively flattens nested dictionaries and lists into a structured key-value text format.
*   **Text/CSV/Log:** Reads file content directly using standard UTF-8 decoding (ignoring parsing errors gracefully).

### 3. Relevance Filtering (`scraper.py`)
To prevent irrelevant files from flooding the database, extracted text is analyzed against a keyword lexicon:
*   **Lexicon Scope:** Includes over 50 keywords divided into Meteorologic Forecasting, Indian hazards (e.g., cloudburst, storm surge, cold wave), Agromet terms (GKMS, crop, kharif), Coastal parameters, and Indian regional names (mausam, chakravat, toofan).
*   **Auto-Trust Rule:** Skip keywords checks and auto-trust documents hailing from official domains: `imd.gov.in`, `ndma.gov.in`, or `incois.gov.in`.

### 4. Alert Adaptation & Normalization (`adapter.py`)
After a source passes relevance filtering, the [`WeatherAlertAdapter`](file:///c:/Users/Tahmeed%20Alam/.gemini/antigravity-ide/scratch/WeatherGPT/backend/services/ingestion/adapter.py) refines the text:
*   **Location Extraction:** Compiles a regex combining a comprehensive roster of Indian States, UTs, and major cities/districts (sorted descending by string length to match long names like "Jammu and Kashmir" before "Jammu"). Matches are title-cased.
*   **Severity Mapping:**
    *   **Extreme:** If keywords like *red alert, extremely severe, catastrophic, cloudburst, landslide disaster* are matched.
    *   **High:** If keywords like *warning, orange alert, heavy rainfall, cyclone, flood alert* are matched.
    *   **Moderate:** Default mapping.
*   **Title/Description Tuning:** Extracts first line (under 120 chars) as title (falling back to filename). Cleaned text is prefixed with its mapped location context, e.g. `[Location: Kolkata] ...`.

### 5. High-Throughput Batch Ingestion (`ingest.py`)
Exposes `/api/v1/ingest/batch` running extraction tasks concurrently across a `ThreadPoolExecutor` (configurable `max_workers` up to 50). It outputs execution statistics (succeeded, failed counts) and appends valid alerts thread-safely via lock to the live system memory.

---

## 🧠 The RAG Pipeline (`rag`)

### 1. Vector Database Ingestion
*   Triggered manually via `/rag/ingest` or automatically.
*   Uses `PyPDFLoader` to read documents from `backend/data/`.
*   Uses LangChain's `RecursiveCharacterTextSplitter` with:
    *   `chunk_size`: 1000 characters
    *   `chunk_overlap`: 150 characters
*   Embeds chunks using Google GenAI embeddings (`models/gemini-embedding-001`).
*   Stores and indexes them inside a local Chroma database directory at `backend/vector_db/`.

### 2. Guardrails & Routing (`brain.py`)
To filter out off-topic queries, the brain applies verification rules:
*   **Domain Matching:** Checks if a location is resolved, or if the user query contains a key weather keyword (e.g., rain, cyclone, temperature, umbrella, travel, NDMA, etc.).
*   **Fallback:** If the query is off-topic, it returns a standard greeting: *"I am WeatherGPT and can help with weather and disaster-safety questions."* bypasses Chroma/Gemini to conserve LLM tokens.

### 3. Context Construction & Semantic Search
*   Retrieves the top `k=3` relevant chunks using `similarity_search_with_relevance_scores` from ChromaDB.
*   Retrieves active live alerts corresponding to the target location.
*   Packages the metadata, page numbers, and snippet sources (e.g., `bulletin.pdf (Page 2)`).
*   Constructs a highly detailed prompt instructing the model to act in **MoES Authority Mode**.

### 4. Authority Mode & LLM Generation
The prompt enforces the following guidelines to `gemini-1.5-flash`:
1.  **Strict Ranking:** Start with red alerts/special bulletins, follow with regional RMC or hydrology updates, and then agromet/marine advisories.
2.  **Agency Citations:** Explicitly mention where the source was fetched from (e.g., *"According to RMC Kolkata..."*, *"Based on INCOIS marine data..."*).
3.  **Balanced Safety Warnings:** If a user asks "Is it safe to go out?", even if there's no active red alert, cross-reference high humidity or thunderstorms in the context to offer warning guidelines.
4.  **No Hallucinations:** Differentiate live weather numbers from static guidance text and restrict inventiveness.

---

## 🇮🇳 15-Language Indic National Matrix

WeatherGPT features native bilingual and regional synthesis supporting 15 languages, integrated via the Government of India **Bhashini ULCA NMT Pipeline** with seamless **Deep-Translator fallback** and synchronized neural voice synthesis via Microsoft Edge-TTS:

| # | Code | Language | Native Script | Primary Engine | Edge-TTS Voice Persona |
|:---|:---|:---|:---|:---|:---|
| 1 | `en` | Indian English | English | Direct / MoES Authority | `en-IN-NeerjaExpressiveNeural` (Female) |
| 2 | `hi` | Hindi | हिन्दी | Bhashini ULCA / NMT | `hi-IN-SwaraNeural` (Female) |
| 3 | `bn` | Bengali | বাংলা | Bhashini ULCA / NMT | `bn-IN-TanishaaNeural` (Female) |
| 4 | `ta` | Tamil | தமிழ் | Bhashini ULCA / NMT | `ta-IN-PallaviNeural` (Female) |
| 5 | `te` | Telugu | తెలుగు | Bhashini ULCA / NMT | `te-IN-ShrutiNeural` (Female) |
| 6 | `mr` | Marathi | मराठी | Bhashini ULCA / NMT | `mr-IN-AarohiNeural` (Female) |
| 7 | `gu` | Gujarati | ગુજરાતી | Bhashini ULCA / NMT | `gu-IN-DhwaniNeural` (Female) |
| 8 | `kn` | Kannada | ಕನ್ನಡ | Bhashini ULCA / NMT | `kn-IN-SapnaNeural` (Female) |
| 9 | `ml` | Malayalam | മലയാളം | Bhashini ULCA / NMT | `ml-IN-SobhanaNeural` (Female) |
| 10 | `ur` | Urdu | اردو | Bhashini ULCA / NMT | `ur-IN-GulNeural` (Female) |
| 11 | `pa` | Punjabi | ਪੰਜਾਬੀ | Bhashini ULCA / NMT | `pa-IN-OjasNeural` (Male) |
| 12 | `or` | Odia | ଓଡ଼ିଆ | Bhashini ULCA / NMT | `hi-IN-SwaraNeural` (Adaptive) |
| 13 | `as` | Assamese | অসমীয়া | Bhashini ULCA / NMT | `bn-IN-TanishaaNeural` (Adaptive) |
| 14 | `sa` | Sanskrit | संस्कृतम् | Bhashini ULCA / NMT | `hi-IN-SwaraNeural` (Adaptive) |
| 15 | `ne` | Nepali | नेपाली | Bhashini ULCA / NMT | `ne-NP-HemkalaNeural` (Female) |

---

## ⏱️ Historical Time-Series Analysis (1H to 7D)

The Bloomberg-style `LOCAL_ENV` telemetry console incorporates real-time temporal analysis across selectable intervals:
- `[1H]` : Most recent hour sensor telemetry
- `[6H]` : 6-hour nowcast trend & average
- `[24H]`: Full 24-hour diurnal cycle comparison
- `[48H]`: 48-hour barometric & precipitation evolution
- `[7D]` : 7-day synoptic trend

When an interval is selected, the **Big Digits Temperature** widget and **Humidity Ratio bar** recalculate the period average, and the AI agent automatically formulates comparative synoptic reasoning:
> *"Compare the current low-pressure system with the data from the last [Selected Interval]."*

---

## 🚨 Out-of-Terminal Emergency Disaster Bridge

In crisis scenarios (Red Alert or High/Extreme severity hazard detection), WeatherGPT initiates out-of-terminal dissemination via the Twilio WhatsApp & SMS bridge (`backend/services/alerts/notifier.py`):
```text
🚨 WEATHER-GPT RED ALERT: [Hazard Type] in [City]. Follow NDRF SOPs. Check terminal for details.
```
*(Formatted under 160 characters for low-bandwidth cellular transmission).*

---

## 🚀 API Endpoints

### 1. Check System Health
```bash
GET http://127.0.0.1:8000/health
```

### 2. Historical Meteorological Time-Series
```bash
GET http://127.0.0.1:8000/weather/history?lat=22.5726&lon=88.3639&interval=24h
```

### 3. Ingest Bulletins (Vector DB)
On startup, WeatherGPT automatically builds the Chroma index from PDFs in
`backend/data/` if no successful local index exists. The marker prevents repeat
embedding work on ordinary process restarts. This endpoint remains available to
manually refresh the index after changing those local PDFs.
```bash
POST http://127.0.0.1:8000/rag/ingest
```

### 3. Concurrent Batch Ingest (Scraper)
Scrape and process a batch of URLs/files in parallel.
```bash
POST http://127.0.0.1:8000/api/v1/ingest/batch
Content-Type: application/json

{
  "sources": [
    "https://mausam.imd.gov.in/kolkata/",
    "backend/data/national_bulletin.pdf"
  ],
  "max_workers": 10
}
```

### 4. RAG Chat
Sends queries to WeatherGPT. Returns weather data, live alerts, generated reply, and source citations.
```bash
POST http://127.0.0.1:8000/chat
Content-Type: application/json

{
  "query": "Is it safe to go outside in Mumbai, and are there any heavy rain warnings?",
  "location": {
    "city": "Mumbai"
  },
  "language": "en"
}
```

---

## 💻 Local Setup & Execution

1.  **Configure Environment:**
    Create a `backend/.env` file with your Google Gemini credentials:
    ```env
    GEMINI_API_KEY=your_gemini_api_key_here
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r backend/requirements.txt
    ```

3.  **Execute Link Hunter manually (optional):**
    ```bash
    python backend/services/ingestion/hunter.py
    ```

4.  **Run Dev Server:**
    ```bash
    uvicorn backend.main:app --reload
    ```
    *   Backend API documentation will be available at `http://127.0.0.1:8000/docs`.
    *   Interactive UI will be served at `http://127.0.0.1:8000/`.

## Render deployment notes

The server starts both background jobs by default:

- `AUTO_RAG_INGEST=true` builds the RAG index when it is missing, before the
  app accepts requests.
- `AUTO_HUNTER=true` starts the bulletin link hunter in the background and
  adds discovered alerts to the live service.
- `WEATHER_CACHE_TTL_SECONDS=600` caches each location's complete Open-Meteo
  response for ten minutes. This is especially important on Render, where
  public Open-Meteo traffic can share a rate-limited outbound IP.
- `ENABLE_API_DOCS=false` disables `/docs`, `/redoc`, and `/openapi.json`.
  This is the secure default for a public deployment.

Set either `AUTO_RAG_INGEST=false` or `AUTO_HUNTER=false` in Render Environment
when troubleshooting. If you run more than one web worker/instance, set
`AUTO_HUNTER=false` for the web service and run the hunter only once as a Render
Cron Job; otherwise every worker will independently scrape the same sources.

For local API exploration only, start the server with `ENABLE_API_DOCS=true`;
do not set that value in Render unless the API specification is intended to be
public.

### Run the hunter from a Render Shell

Open **Shell** for the running web service and execute this from the repository
root:

```bash
python -m backend.services.ingestion.hunter
```

The command automatically uses Render's `PORT`. If it is executed from a
separate cron service instead of the web service shell, configure
`INGEST_API_URL=https://your-service.onrender.com/api/v1/ingest/batch` and set
the same `INGEST_API_TOKEN` value on both services.

### Do you need Docker?

Not for this app's first Render deployment. Render can install
`backend/requirements.txt` and run `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
directly. Docker becomes useful only when you need to pin OS-level packages,
make local and production environments identical, or run multiple services from
one reproducible image. Start without it; the automatic jobs and cache above do
not depend on Docker.
