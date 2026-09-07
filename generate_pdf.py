"""
WeatherGPT: Comprehensive Technical & Architectural Briefing PDF Generator
Generates a publication-grade executive PDF document with embedded system architecture diagram.
"""
import base64
import os
import subprocess
import sys
from pathlib import Path

# Paths
WORKSPACE_ROOT = Path(__file__).resolve().parent
HTML_PATH = WORKSPACE_ROOT / "WeatherGPT_Technical_Briefing.html"
PDF_PATH = WORKSPACE_ROOT / "WeatherGPT_Technical_Briefing.pdf"

# Find image artifact
IMAGE_PATH = Path(r"C:\Users\Tahmeed Alam\.gemini\antigravity-ide\brain\45c93522-659e-4d74-a6a9-96c0a3455889\weathergpt_system_architecture_1788721662216.jpg")
if not IMAGE_PATH.exists():
    # Try searching for architecture jpg in the brain folder
    brain_dir = Path(r"C:\Users\Tahmeed Alam\.gemini\antigravity-ide\brain\45c93522-659e-4d74-a6a9-96c0a3455889")
    candidates = list(brain_dir.glob("weathergpt_system_architecture*.jpg"))
    if candidates:
        IMAGE_PATH = candidates[0]

img_b64 = ""
if IMAGE_PATH.exists():
    with open(IMAGE_PATH, "rb") as img_file:
        img_b64 = base64.b64encode(img_file.read()).decode("utf-8")

img_tag = f'<img src="data:image/jpeg;base64,{img_b64}" alt="WeatherGPT System Architecture" class="arch-diagram" />' if img_b64 else '<p><em>[System Architecture Diagram]</em></p>'

HTML_CONTENT = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>WeatherGPT: Comprehensive Technical & Architectural Briefing</title>
<style>
  @page {{
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @bottom-right {{
      content: counter(page);
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 9pt;
      color: #718096;
    }}
  }}

  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #1a202c;
    line-height: 1.55;
    font-size: 10pt;
    margin: 0;
    padding: 0;
    background-color: #ffffff;
  }}

  .header-card {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0369a1 100%);
    color: #ffffff;
    padding: 24px 28px;
    border-radius: 10px;
    margin-bottom: 24px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  }}

  .header-card h1 {{
    margin: 0 0 6px 0;
    font-size: 20pt;
    letter-spacing: -0.5px;
    color: #38bdf8;
    font-weight: 700;
  }}

  .header-card .subtitle {{
    font-size: 11pt;
    color: #e2e8f0;
    margin: 0 0 12px 0;
    font-weight: 400;
  }}

  .header-badges {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 8.5pt;
  }}

  .badge {{
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.25);
    padding: 3px 10px;
    border-radius: 9999px;
    color: #f8fafc;
    font-weight: 500;
  }}

  h2 {{
    color: #0f172a;
    font-size: 13pt;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 5px;
    margin-top: 22px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    page-break-after: avoid;
  }}

  h3 {{
    color: #0369a1;
    font-size: 10.5pt;
    margin-top: 14px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }}

  p {{
    margin: 0 0 10px 0;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 18px 0;
    font-size: 9pt;
    page-break-inside: avoid;
  }}

  th, td {{
    padding: 7px 10px;
    text-align: left;
    vertical-align: top;
    border: 1px solid #cbd5e1;
  }}

  th {{
    background-color: #0f172a;
    color: #f8fafc;
    font-weight: 600;
    font-size: 9pt;
  }}

  tr:nth-child(even) td {{
    background-color: #f8fafc;
  }}

  .feature-num {{
    font-weight: 700;
    color: #0284c7;
    width: 32px;
    text-align: center;
  }}

  .code-inline {{
    background-color: #f1f5f9;
    color: #0f172a;
    padding: 1px 5px;
    border-radius: 4px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 8.5pt;
    border: 1px solid #e2e8f0;
  }}

  .arch-container {{
    text-align: center;
    margin: 16px 0;
    page-break-inside: avoid;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px;
    background: #0f172a;
  }}

  .arch-diagram {{
    width: 100%;
    max-height: 480px;
    object-fit: contain;
    border-radius: 6px;
    display: block;
  }}

  .arch-caption {{
    font-size: 8.5pt;
    color: #94a3b8;
    margin-top: 8px;
    font-style: italic;
  }}

  .roadmap-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 14px 0 18px 0;
    page-break-inside: avoid;
  }}

  .roadmap-col {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-top: 3px solid #0284c7;
    border-radius: 6px;
    padding: 10px 12px;
  }}

  .roadmap-col h4 {{
    margin: 0 0 6px 0;
    color: #0f172a;
    font-size: 9.5pt;
    font-weight: 700;
  }}

  .roadmap-col ul {{
    margin: 0;
    padding-left: 16px;
    font-size: 8.5pt;
    color: #334155;
  }}

  .roadmap-col li {{
    margin-bottom: 5px;
  }}

  .page-break {{
    page-break-before: always;
  }}

  .callout {{
    background-color: #f0f9ff;
    border-left: 4px solid #0284c7;
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    margin: 12px 0;
    font-size: 9pt;
  }}

  .footer-note {{
    margin-top: 24px;
    padding-top: 12px;
    border-top: 1px solid #e2e8f0;
    font-size: 8pt;
    color: #64748b;
    text-align: center;
  }}
</style>
</head>
<body>

  <!-- HEADER -->
  <div class="header-card">
    <h1>WeatherGPT: Technical & Architectural Briefing</h1>
    <div class="subtitle">AI-Powered Conversational Platform for Multilingual Meteorological Intelligence & Multi-Hazard Early Warnings</div>
    <div class="header-badges">
      <span class="badge">Problem Statement: SIH 2026</span>
      <span class="badge">Ministry of Earth Sciences (MoES)</span>
      <span class="badge">22 Scheduled Indian Languages</span>
      <span class="badge">Deterministic SSoT Sovereignty</span>
      <span class="badge">Live Production Prototype</span>
    </div>
  </div>

  <!-- SECTION 1: WORKING PROTOTYPE FEATURES -->
  <h2>1. Features in the Working Prototype (Demonstration-Ready)</h2>
  <p>The WeatherGPT system is fully operational end-to-end, solving the critical data fragmentation between meteorological bulletins, satellite models, and disaster warnings through conversational intelligence:</p>

  <table>
    <thead>
      <tr>
        <th class="feature-num">#</th>
        <th style="width: 28%;">Feature Capability</th>
        <th>Engineering Implementation & Live Behavior</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="feature-num">1</td>
        <td><strong>Deterministic Linguistic Sovereignty (22+1 Languages)</strong></td>
        <td>Single Source of Truth (SSoT) architecture across all <strong>22 Eighth-Schedule Indian languages + Indian English</strong>. UI dropdown strictly dictates downstream processing; auto-detect coin-flips and false <span class="code-inline">SCRIPT_MISMATCH</span> rejections are eliminated.</td>
      </tr>
      <tr>
        <td class="feature-num">2</td>
        <td><strong>Voice-to-Voice Command Center</strong></td>
        <td>Seamless full-duplex voice loop: <strong>FFmpeg 16 kHz Mono WAV audio standardisation</strong>, local int8 CPU-quantized <strong>Faster-Whisper</strong> STT, and <strong>Microsoft Edge-TTS</strong> neural speech synthesis with Base64 HTML5 instant playback.</td>
      </tr>
      <tr>
        <td class="feature-num">3</td>
        <td><strong>Acoustic Token Mapping for Rare Indic Languages</strong></td>
        <td>Maps non-standard languages (<span class="code-inline">kok</span>, <span class="code-inline">mai</span>, <span class="code-inline">brx</span>, <span class="code-inline">doi</span>, <span class="code-inline">ks</span>, <span class="code-inline">sd</span>, <span class="code-inline">mni</span>, <span class="code-inline">sat</span>, <span class="code-inline">or</span>) to optimal acoustic surrogate models (<span class="code-inline">mr</span>, <span class="code-inline">hi</span>, <span class="code-inline">ur</span>, <span class="code-inline">bn</span>) with native weather keyword priming, preventing Whisper <span class="code-inline">ValueError</span> crashes.</td>
      </tr>
      <tr>
        <td class="feature-num">4</td>
        <td><strong>Brahmi Odia (<span class="code-inline">OR</span>) Speech Synthesis</strong></td>
        <td>Applies mathematical Brahmi transliteration (<span class="code-inline">deva = odia - 0x0200</span>) exclusively for <span class="code-inline">hi-IN-SwaraNeural</span> voice synthesis. Overcomes Edge-TTS's lack of an Odia voice to synthesize 100% authentic spoken Odia while preserving pure Odia script in chat.</td>
      </tr>
      <tr>
        <td class="feature-num">5</td>
        <td><strong>Strict Temporal Intent & Hard Date Locking</strong></td>
        <td>Categorizes queries into <em>Current</em>, <em>Tomorrow/Future</em>, <em>Safety</em>, or <em>Historical Archive</em>. Automatically anchors historical dates (e.g. Sept 4th or Cyclone Amphan) to exact dates, reporting in past tense and strictly suppressing live telemetry.</td>
      </tr>
      <tr>
        <td class="feature-num">6</td>
        <td><strong>Real-Time Multi-Hazard Telemetry & Geocoding</strong></td>
        <td>Integrated with <strong>Open-Meteo API</strong> (temperature, humidity, wind, precipitation) and real-time <strong>IMD Disaster Bulletins</strong> & <strong>USGS Earthquake Feeds</strong> for instant situational awareness.</td>
      </tr>
      <tr>
        <td class="feature-num">7</td>
        <td><strong>Synoptic System & Oceanic Tracking</strong></td>
        <td>Automated detection of marine low-pressure systems, depressions, and cyclonic circulations across <strong>Bay of Bengal</strong> and <strong>Arabian Sea</strong> with coordinates, bounds, and severity levels.</td>
      </tr>
      <tr>
        <td class="feature-num">8</td>
        <td><strong>Dual-Modal Display & Pure Native Speech</strong></td>
        <td>Chat UI renders regional native script followed by an English markdown reference version (<span class="code-inline">---</span>). Spoken audio is strictly filtered to 100% native words with numbers and units expanded into native language terms.</td>
      </tr>
      <tr>
        <td class="feature-num">9</td>
        <td><strong>Red Alert Emergency WhatsApp Bridge</strong></td>
        <td>Civil defence dispatch module automatically generates out-of-terminal WhatsApp alerts when critical meteorological hazards or Red Alerts are declared.</td>
      </tr>
      <tr>
        <td class="feature-num">10</td>
        <td><strong>Multi-Tier RAG IMD Document Brain</strong></td>
        <td>Semantic document vector search over official IMD synoptic weather bulletins and MoES guidelines powered by <strong>ChromaDB</strong> and <strong>Google Gemini Embeddings</strong>.</td>
      </tr>
    </tbody>
  </table>

  <!-- PAGE BREAK -->
  <div class="page-break"></div>

  <!-- SECTION 2: SYSTEM ARCHITECTURE -->
  <h2>2. System Architecture Blueprint</h2>
  <p>The enterprise platform is organized into 5 decoupled, fault-tolerant tiers:</p>

  <div class="arch-container">
    {img_tag}
    <div class="arch-caption">Figure 1: WeatherGPT 5-Tier End-to-End System Architecture (Ingestion, Processing, AI Brain, Data, and Synthesis)</div>
  </div>

  <div class="callout">
    <strong>Architectural Principle: Single Source of Truth (SSoT)</strong><br>
    Linguistic sovereignty is deterministic: the user's selected language strictly binds Whisper STT acoustic priming, RAG monolingual system constraints, script verification, and Edge-TTS voice assignment, preventing probabilistic drift and Maltese/foreign classification errors.
  </div>

  <!-- SECTION 3: TECHNOLOGIES USED & ROADMAP ADDITIONS -->
  <h2>3. Technologies Used & Future Extensions</h2>

  <table>
    <thead>
      <tr>
        <th style="width: 25%;">Layer / Subsystem</th>
        <th style="width: 35%;">Currently Implemented Stack</th>
        <th>Future Roadmap Extensions</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>API & Runtime</strong></td>
        <td>Python 3.10+, <strong>FastAPI</strong>, Starlette, Uvicorn (Asynchronous REST & SSE streaming)</td>
        <td>Docker containers, Kubernetes orchestration, Redis distributed caching.</td>
      </tr>
      <tr>
        <td><strong>Generative AI & LLM</strong></td>
        <td><strong>Google Gemini 3.6 Flash / 3.5 Flash</strong> via LangChain with automated dual-model failover</td>
        <td>Fine-tuned meteorological SLMs (DeepSeek / Llama-3 8B) hosted on edge servers.</td>
      </tr>
      <tr>
        <td><strong>Vector DB & Embeddings</strong></td>
        <td><strong>ChromaDB</strong> (local vector store), <strong>models/gemini-embedding-001</strong></td>
        <td>Qdrant distributed cluster, automated IMD PDF OCR ingestion pipeline.</td>
      </tr>
      <tr>
        <td><strong>Speech-to-Text (STT)</strong></td>
        <td><strong>Faster-Whisper (CPU int8)</strong> with acoustic surrogate token mapping</td>
        <td>On-premise GPU-accelerated Whisper-Large-v3, fine-tuned Bhashini ULCA ASR.</td>
      </tr>
      <tr>
        <td><strong>Speech Synthesis (TTS)</strong></td>
        <td><strong>Microsoft Edge-TTS</strong> neural voices with Brahmi transliteration engine</td>
        <td>Bhashini Coqui / VITS open-source acoustic models for tribal Indian dialects.</td>
      </tr>
      <tr>
        <td><strong>Translation Gateway</strong></td>
        <td>Digital India <strong>Bhashini ULCA NMT</strong> + Google Translator + Gemini Flash fallback</td>
        <td>Offline IndicTrans2 neural translation container with zero cloud dependencies.</td>
      </tr>
      <tr>
        <td><strong>Telemetry & Hazards</strong></td>
        <td><strong>Open-Meteo API</strong>, IMD RSS Bulletins, <strong>USGS Real-Time Earthquake API</strong></td>
        <td>Direct GRIB2/NetCDF4 NWP ingestion (WRF/GFS/NCMRWF), Doppler Weather Radar feeds.</td>
      </tr>
      <tr>
        <td><strong>Frontend & Visualization</strong></td>
        <td>Vanilla HTML5, Modern CSS, ES6 JavaScript, Web Audio API</td>
        <td>Mapbox GL JS / WebGL wind particle vector shaders, Leaflet isobar contours.</td>
      </tr>
    </tbody>
  </table>

  <!-- SECTION 4: FUTURE IMPROVISATION ROADMAP -->
  <h2>4. Future Improvisations & Production Scaling Roadmap</h2>

  <div class="roadmap-grid">
    <div class="roadmap-col">
      <h4>Phase 1: Near-Term</h4>
      <ul>
        <li><strong>NWP GRIB2 Ingestion:</strong> Direct extraction of WRF / GFS 3 km simulation grids from MoES clusters.</li>
        <li><strong>Fluid Wind Particle Shaders:</strong> WebGL animated flow-field overlays on the interactive map.</li>
        <li><strong>Historical Trend Graphs:</strong> Interactive SVG bar/line charts for multi-day precipitation trends.</li>
      </ul>
    </div>
    <div class="roadmap-col">
      <h4>Phase 2: Mid-Term</h4>
      <ul>
        <li><strong>Doppler Radar Overlays:</strong> Real-time DWR reflectivity (dBZ) and radial velocity nowcasts.</li>
        <li><strong>Local Bhashini VITS:</strong> On-premise neural acoustic models for authentic tribal accents (Bodo, Santali).</li>
        <li><strong>Multi-Channel Broadcast:</strong> Automated SMS & Twilio automated voice calling for emergency zones.</li>
      </ul>
    </div>
    <div class="roadmap-col">
      <h4>Phase 3: Long-Term</h4>
      <ul>
        <li><strong>Offline Mesh Protocol:</strong> LoRaWAN and IVR telephone network for fishermen and farmers without internet.</li>
        <li><strong>INSAT-3D Satellite Feed:</strong> Live thermal infrared (TIR) and water-vapor multispectral animation loops.</li>
        <li><strong>Crowdsourced IoT Telemetry:</strong> Micro-climate urban flood sensors and citizen verification.</li>
      </ul>
    </div>
  </div>

  <div class="footer-note">
    WeatherGPT — Ministry of Earth Sciences (MoES) Meteorological Conversational Intelligence Platform | Smart India Hackathon (SIH) 2026
  </div>

</body>
</html>
"""

# Configure stdout to UTF-8 to prevent Windows cp1252 crashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Write HTML file
with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print(f"[OK] Generated print-ready HTML: {HTML_PATH}")

# Search for Edge or Chrome executable to convert HTML to PDF
BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

browser_exe = next((p for p in BROWSER_CANDIDATES if os.path.exists(p)), None)

if browser_exe:
    print(f"[INFO] Found browser rendering engine: {browser_exe}")
    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={PDF_PATH}",
        str(HTML_PATH.resolve()),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if PDF_PATH.exists() and PDF_PATH.stat().st_size > 0:
            print(f"[SUCCESS] Professional PDF created at: {PDF_PATH.resolve()} ({PDF_PATH.stat().st_size // 1024} KB)")
            sys.exit(0)
        else:
            print(f"[WARN] Browser print completed but PDF size was 0: {proc.stderr}")
    except Exception as e:
        print(f"[WARN] Headless browser render encountered an error: {e}")
else:
    print("[INFO] No Edge/Chrome executable automatically detected in default program directories.")

print(f"[INFO] You can also open the HTML file directly in your browser and press Ctrl+P -> Save as PDF:\n   {HTML_PATH.resolve()}")
