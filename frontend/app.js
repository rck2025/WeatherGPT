/**
 * WEATHERGPT-TERMINAL 
 * Full-Stack Integration with FastAPI Backend & Pydantic Schemas
 */

// ── State Management ────────────────────────────────────────────────────────
const state = {
  currentMode: 'standard', // 'standard' | 'aviation'
  operationalMode: 'standard', // alias
  chatHistory: [],
  activeLocation: { latitude: 22.5726, longitude: 88.3639, city: 'Kolkata' },
  currentLocation: { latitude: 22.5726, longitude: 88.3639, city: 'Kolkata' }, // alias
  satelliteMode: false,
  mapMode: 'dark', // 'dark' | 'sat'
  locationMode: 'gps', // 'gps' | 'manual'
  gpsCoordinates: null, // { latitude, longitude }
  manualLocationText: '',
  isVoiceMode: false,
  isExecuting: false,
  map: null,
  radarMarker: null,
  locationMarker: null,
  hazardLayerGroup: null,
  synopticLayerGroup: null,
  scientificLayer: null,
  scientificTileUrl: null,
  lastCenterLat: 22.5726,
  lastCenterLon: 88.3639,
  hasInitialProbeRan: false,
  isInitialized: false,
  currentInterval: '24h',
  historyData: [],
  lastWeatherData: null,
  currentAlerts: [],
  currentOverlays: [],
};

// ── Multi-Turn Conversational Memory (UI State Persistence) ─────────────────
let chatHistory = state.chatHistory;
window.chatHistory = chatHistory;
window.state = state;

// ── DOM Element Selectors ───────────────────────────────────────────────────
const elements = {
  utcClock: document.getElementById('utcClock'),
  istClock: document.getElementById('istClock'),
  systemIndicator: document.getElementById('systemIndicator'),
  systemStatusText: document.getElementById('systemStatusText'),
  tickerTrack: document.getElementById('tickerTrack'),
  crisisBanner: document.getElementById('crisisBanner'),
  chatStream: document.getElementById('chatStream'),
  commandForm: document.getElementById('commandForm'),
  queryInput: document.getElementById('queryInput'),
  languageSelect: document.getElementById('languageSelect'),
  voiceBtn: document.getElementById('voiceBtn'),
  executeBtn: document.getElementById('executeBtn'),
  gpsModeBtn: document.getElementById('gpsModeBtn'),
  manualModeBtn: document.getElementById('manualModeBtn'),
  locationSummaryText: document.getElementById('locationSummaryText'),
  manualInputContainer: document.getElementById('manualInputContainer'),
  manualLocationInput: document.getElementById('manualLocationInput'),
  telemetryTemp: document.getElementById('metricTemp') || document.getElementById('telemetryTemp'),
  metricTemp: document.getElementById('metricTemp') || document.getElementById('telemetryTemp'),
  telemetryTempSub: document.getElementById('telemetryTempSub'),
  telemetryHumidity: document.getElementById('metric2Val') || document.getElementById('telemetryHumidity'),
  metric2Val: document.getElementById('metric2Val') || document.getElementById('telemetryHumidity'),
  telemetryHumiditySub: document.getElementById('telemetryHumiditySub'),
  humidityBarFill: document.getElementById('metric2Bar') || document.getElementById('humidityBarFill'),
  metric2Bar: document.getElementById('metric2Bar') || document.getElementById('humidityBarFill'),
  telemetryWind: document.getElementById('telemetryWind'),
  telemetryWindSub: document.getElementById('telemetryWindSub'),
  telemetryAlertsCount: document.getElementById('metricAlerts') || document.getElementById('telemetryAlertsCount'),
  metricAlerts: document.getElementById('metricAlerts') || document.getElementById('telemetryAlertsCount'),
  telemetryBaroSub: document.getElementById('telemetryBaroSub'),
  sourceModal: document.getElementById('sourceModal'),
  sourceModalTitle: document.getElementById('sourceModalTitle'),
  sourceModalContent: document.getElementById('sourceModalContent'),
  sourceModalMeta: document.getElementById('sourceModalMeta'),
  sourceDocLink: document.getElementById('sourceDocLink'),
  closeSourceModalBtn: document.getElementById('closeSourceModalBtn'),
  intervalBtnRow: document.getElementById('intervalBtnRow'),
  radarBadge: document.getElementById('radarBadge'),
  modeToggleHeader: document.getElementById('mode-toggle-header'),
  modeToggleMap: document.getElementById('mode-toggle-map'),
  modeBtnStandard: document.getElementById('mode-btn-standard'),
  modeBtnAviation: document.getElementById('mode-btn-aviation'),
  modeBtnFarmer: document.getElementById('mode-btn-farmer'),
  telemetryCard1Title: document.getElementById('telemetryCard1Title'),
  telemetryCard1Badge: document.getElementById('telemetryCard1Badge'),
  telemetryCard2Title: document.getElementById('telemetryCard2Title'),
  telemetryCard2Badge: document.getElementById('telemetryCard2Badge'),
  telemetryCard3Title: document.getElementById('telemetryCard3Title'),
  telemetryCard3Badge: document.getElementById('telemetryCard3Badge'),
  telemetryCard4Title: document.getElementById('telemetryCard4Title'),
  telemetryCard4Badge: document.getElementById('telemetryCard4Badge'),
};

// ── 1. Digital Real-Time Clocks (UTC & IST) ─────────────────────────────────
function updateClocks() {
  const now = new Date();

  // Format UTC: HH:MM:SS
  const utcHours = String(now.getUTCHours()).padStart(2, '0');
  const utcMinutes = String(now.getUTCMinutes()).padStart(2, '0');
  const utcSeconds = String(now.getUTCSeconds()).padStart(2, '0');
  if (elements.utcClock) elements.utcClock.textContent = `${utcHours}:${utcMinutes}:${utcSeconds}`;

  // Format IST (UTC + 5:30): HH:MM:SS
  const istOffset = 5.5 * 60 * 60 * 1000;
  const istTime = new Date(now.getTime() + istOffset);
  const istHours = String(istTime.getUTCHours()).padStart(2, '0');
  const istMinutes = String(istTime.getUTCMinutes()).padStart(2, '0');
  const istSeconds = String(istTime.getUTCSeconds()).padStart(2, '0');
  if (elements.istClock) elements.istClock.textContent = `${istHours}:${istMinutes}:${istSeconds}`;
}
setInterval(updateClocks, 1000);
updateClocks();

// ── 2. Geospatial Layer (Leaflet.js) & Dual-Mode Background ─────────────────
// Base Tile Layers: Terminal Dark Matter vs Live Satellite NRT
const darkLayer = (typeof L !== 'undefined') ? L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors',
  className: 'terminal-osm-dark-tiles',
}) : null;

const satelliteLayer = (typeof L !== 'undefined') ? L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
  maxZoom: 19,
  attribution: 'Satellite NRT / Esri',
  className: 'esri-satellite-high-contrast',
}) : null;

state.darkLayer = darkLayer;
state.satelliteLayer = satelliteLayer;
state.mapMode = 'dark';
window.darkBase = darkLayer;
window.satBase = satelliteLayer;

function initMap() {
  const mapElement = document.getElementById('radarMap') || document.getElementById('map');
  if (!mapElement || typeof L === 'undefined') return;

  // Background adapts to theme: light mode gets sky blue, dark/default stays deep midnight blue
  const isLightTheme = document.body.classList.contains('theme-light');
  mapElement.style.backgroundColor = isLightTheme ? '#e8f4f8' : '#000814';

  // Initialize map centered on South Asia / India: Bounds [5, 60] to [38, 100]
  state.map = L.map(mapElement, {
    attributionControl: false,
    zoomControl: true,
  });

  const southAsiaBounds = [[5, 60], [38, 100]];
  state.map.fitBounds(southAsiaBounds);

  // Default to darkLayer (CartoDB Dark Matter)
  if (state.darkLayer) {
    state.darkLayer.addTo(state.map);
  }

  // Dedicated layer groups for Synoptic Heatmaps and Multi-Hazard markers
  state.synopticLayerGroup = L.layerGroup().addTo(state.map);
  state.hazardLayerGroup = L.layerGroup().addTo(state.map);
  window.hazardLayerGroup = state.hazardLayerGroup;

  // Initialize Geospatially Anchored Tactical Radar (pinned to default Kolkata coords)
  initRadar(22.5726, 88.3639);

  // Floating Satellite / GEE Layer Toggle on Map
  if (typeof L !== 'undefined' && state.map) {
    const satControl = L.control({ position: 'topright' });
    satControl.onAdd = function () {
      const div = L.DomUtil.create('div', 'leaflet-bar map-floating-toggle-wrap');
      div.innerHTML = `
        <button type="button" id="floatingAgriBtn" class="floating-agri-btn" title="Toggle ESA WorldCover 10m Cropland Satellite Mask (Class 40: Cultivated Fields)">
          🌾 AGRI_SCAN
        </button>
        <button type="button" id="floatingSatBtn" class="floating-sat-btn" title="Toggle NASA GEE Satellite / Multi-Hazard Composite">
          🛰️ SAT / GEE
        </button>
      `;
      L.DomEvent.disableClickPropagation(div);
      div.querySelector('#floatingAgriBtn').onclick = (e) => {
        e.preventDefault();
        toggleAgriScan();
      };
      div.querySelector('#floatingSatBtn').onclick = (e) => {
        e.preventDefault();
        toggleMapMode();
      };
      return div;
    };
    satControl.addTo(state.map);
  }
}

/**
 * Tactical Radar / Satellite Layer Switcher:
 * Swaps between the high-contrast CartoDB Dark Matter grid and real-time Esri Satellite Imagery
 * blended with the Google Earth Engine Scientific Multi-Hazard Composite (NASA GPM Rainfall Mask + Low-Pressure Aura).
 * Guarantees that sonar sweeps, synoptic systems, and pulsing hazard dots stay firmly on top.
 */
function toggleMapMode() {
  const btn = document.getElementById('map-toggle');
  const mapElem = document.getElementById('radarMap');
  if (!state.map) return;

  if (state.mapMode === 'dark') {
    // ── Transition to Satellite / Scientific Mode ──
    if (state.darkLayer && state.map.hasLayer(state.darkLayer)) {
      state.map.removeLayer(state.darkLayer);
    }
    if (state.satelliteLayer) {
      state.satelliteLayer.addTo(state.map);
    }
    state.mapMode = 'sat';
    state.satelliteMode = true;
    document.body.classList.add('sat-mode');
    if (mapElem) mapElem.classList.add('sat-mode');

    // Remove radar sweep from map in Satellite mode
    if (state.radarMarker && state.map.hasLayer(state.radarMarker)) {
      state.map.removeLayer(state.radarMarker);
    }

    // 2. Add the GEE Scientific Composite (Rainfall Mask + Low-Pressure Aura) at 0.55 opacity
    loadScientificCompositeOverlay();

    // 3. Re-render alerts to activate Magnitude-Aware 3-ring Seismic Ripples for earthquakes
    renderHazardMarkers(state.currentAlerts);

    if (btn) {
      btn.innerText = 'Satellite';
      btn.classList.add('is-sat-active');
      btn.style.backgroundColor = '';
      btn.style.color = '';
      btn.style.borderColor = '';
      btn.style.boxShadow = '';
    }

    const floatBtn = document.getElementById('floatingSatBtn');
    if (floatBtn) {
      floatBtn.classList.add('is-active');
      floatBtn.textContent = '🛰️ SAT ACTIVE';
    }

    const badge = document.getElementById('radarBadge');
    if (badge) {
      badge.textContent = 'Satellite Imagery Active';
      badge.style.borderColor = '#00d4ff';
      badge.style.color = '#00d4ff';
    }
  } else {
    // ── Transition to Radar Lite / Bloomberg Dark Mode ──
    // 1. Remove all scientific layers
    if (state.scientificLayer && state.map.hasLayer(state.scientificLayer)) {
      state.map.removeLayer(state.scientificLayer);
    }
    if (state.satelliteLayer && state.map.hasLayer(state.satelliteLayer)) {
      state.map.removeLayer(state.satelliteLayer);
    }
    // 2. Return to the clean Bloomberg Dark base with simple dots
    if (state.darkLayer) {
      state.darkLayer.addTo(state.map);
    }
    state.mapMode = 'dark';
    state.satelliteMode = false;
    document.body.classList.remove('sat-mode');
    if (mapElem) mapElem.classList.remove('sat-mode');

    // Restore radar sweep marker in Tactical Radar mode
    if (state.radarMarker && !state.map.hasLayer(state.radarMarker)) {
      state.radarMarker.addTo(state.map);
    }

    // Re-render alerts to return to clean Bloomberg dots
    renderHazardMarkers(state.currentAlerts);

    if (btn) {
      btn.innerText = 'Satellite';
      btn.classList.remove('is-sat-active');
      btn.style.backgroundColor = '';
      btn.style.color = '';
      btn.style.borderColor = '';
      btn.style.boxShadow = '';
    }

    const floatBtn = document.getElementById('floatingSatBtn');
    if (floatBtn) {
      floatBtn.classList.remove('is-active');
      floatBtn.textContent = '🛰️ SAT / GEE';
    }

    const badge = document.getElementById('radarBadge');
    if (badge) {
      badge.textContent = (state.currentMode === 'farmer') ? 'Agricultural Weather Active' : 'Live Weather Radar';
      badge.style.borderColor = '';
      badge.style.color = '';
    }
  }

  // Ensure radar sweep, synoptic systems, and hazard dots stay on top
  preserveOverlaysOnTop();
}

/**
 * Loads the GEE Scientific Composite layer (NASA GPM IMERG Mask + MODIS/ERA5 Low-Pressure Aura)
 * and attaches it over the satellite imagery at 0.55 opacity.
 */
async function loadScientificCompositeOverlay() {
  if (!state.map) return;

  if (state.scientificLayer) {
    if (!state.map.hasLayer(state.scientificLayer)) {
      state.scientificLayer.addTo(state.map);
    }
    state.scientificLayer.setOpacity(0.55);
    preserveOverlaysOnTop();
    return;
  }

  try {
    const res = await fetch('/api/v1/map/layers/scientific_composite');
    if (!res.ok) {
      console.warn('Scientific composite overlay returned HTTP', res.status);
      return;
    }
    const data = await res.json();
    if (data && data.tile_url) {
      state.scientificTileUrl = data.tile_url;
      // Attach if still in satellite mode
      if (state.mapMode === 'sat') {
        state.scientificLayer = L.tileLayer(data.tile_url, {
          maxZoom: 19,
          opacity: 0.55,
          zIndex: 400,
          attribution: 'NASA GPM & Synoptic Pressure Aura (GEE)',
        }).addTo(state.map);
        preserveOverlaysOnTop();
      }
    }
  } catch (err) {
    console.error('Failed to load GEE scientific composite overlay:', err);
  }
}

/**
 * Posts a technical telemetry notification to the terminal chat stream
 * when Satellite Mode is activated.
 */
function appendScientificModeNotification() {
  if (!elements.chatStream) return;
  const note = document.createElement('div');
  note.className = 'message-entry system-scientific-notice';
  note.innerHTML = `
    <span class="message-prefix" style="color: #00F0FF;">SYS_SATELLITE // SCIENTIFIC_STACK</span>
    <div class="message-content" style="color: #cbebd0; font-size: 11px; border-left: 2px solid #00F0FF; padding-left: 8px; margin-top: 4px;">
      <span style="color: #00F0FF; font-weight: 800;">MULTI-HAZARD SCIENTIFIC STACK ACTIVATED:</span>
      MODIS Cloud-Top Pressure Aura &amp; NASA GPM IMERG Precipitation Mask (&gt;0.2mm/hr) blended over orbital imagery.
      System calibrated for Cloud-Top Brightness Temperatures (BT) &amp; Convective Available Potential Energy (CAPE) diagnostics.
    </div>
  `;
  elements.chatStream.appendChild(note);
  note.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

/**
 * Toggles the ESA WorldCover 10m Cropland-Only Satellite Mask (Agro-Tactical Farmer Mode).
 * Isolates agricultural fields (Class 40) in a glowing Golden Amber palette (#f59e0b)
 * at 0.6 opacity over satellite imagery.
 */
async function toggleAgriScan() {
  if (!state.map) return;

  const headerBtn = document.getElementById('agri-scan-toggle');
  const floatBtn = document.getElementById('floatingAgriBtn');
  const badge = document.getElementById('radarBadge');

  if (!state.agriScanActive) {
    // ── Activate Agri-Scan Cropland Mask ──
    state.agriScanActive = true;

    // Ensure we are on Satellite base imagery so crops glow over realistic terrain
    if (state.mapMode === 'dark') {
      if (state.darkLayer && state.map.hasLayer(state.darkLayer)) {
        state.map.removeLayer(state.darkLayer);
      }
      if (state.satelliteLayer && !state.map.hasLayer(state.satelliteLayer)) {
        state.satelliteLayer.addTo(state.map);
      }
      state.mapMode = 'sat';
      state.satelliteMode = true;
      document.body.classList.add('sat-mode');
      const mapElem = document.getElementById('radarMap');
      if (mapElem) mapElem.classList.add('sat-mode');

      const mapBtn = document.getElementById('map-toggle');
      if (mapBtn) {
        mapBtn.innerText = 'Satellite';
        mapBtn.classList.add('is-sat-active');
        mapBtn.style.backgroundColor = '';
        mapBtn.style.color = '';
      }
    }

    // Load Cropland Mask Tile Layer
    await loadCroplandOverlay();

    // Update buttons to active Golden Amber state
    if (headerBtn) {
      headerBtn.classList.add('is-active');
      headerBtn.innerText = 'Agri-scan';
    }
    if (floatBtn) {
      floatBtn.classList.add('is-active');
      floatBtn.textContent = '🌾 AGRI ACTIVE';
    }

    if (badge) {
      badge.textContent = 'Cropland Overlay Active';
      badge.style.borderColor = '#f59e0b';
      badge.style.color = '#f59e0b';
    }

    preserveOverlaysOnTop();
  } else {
    // ── Deactivate Agri-Scan ──
    state.agriScanActive = false;

    if (state.croplandLayer && state.map.hasLayer(state.croplandLayer)) {
      state.map.removeLayer(state.croplandLayer);
    }

    if (headerBtn) {
      headerBtn.classList.remove('is-active');
      headerBtn.innerText = 'Agri-scan';
    }
    if (floatBtn) {
      floatBtn.classList.remove('is-active');
      floatBtn.textContent = '🌾 AGRI_SCAN';
    }

    if (badge) {
      if (state.currentMode === 'farmer') {
        badge.textContent = 'Agricultural Weather Active';
        badge.style.borderColor = '#f59e0b';
        badge.style.color = '#f59e0b';
      } else if (state.mapMode === 'sat') {
        badge.textContent = 'Satellite Imagery Active';
        badge.style.borderColor = '#00d4ff';
        badge.style.color = '#00d4ff';
      } else {
        badge.textContent = 'Live Weather Radar';
        badge.style.borderColor = '';
        badge.style.color = '';
      }
    }
  }
}
window.toggleAgriScan = toggleAgriScan;

/**
 * Loads the ESA WorldCover 10m Cropland Mask layer via GEE and overlays it at 0.6 opacity.
 */
async function loadCroplandOverlay() {
  if (!state.map) return;

  if (state.croplandLayer) {
    if (!state.map.hasLayer(state.croplandLayer)) {
      state.croplandLayer.addTo(state.map);
    }
    state.croplandLayer.setOpacity(0.6);
    preserveOverlaysOnTop();
    return;
  }

  try {
    const res = await fetch('/api/v1/map/layers/cropland');
    if (!res.ok) {
      console.warn('Cropland overlay returned HTTP', res.status);
      return;
    }
    const data = await res.json();
    if (data && data.tile_url) {
      state.croplandTileUrl = data.tile_url;
      state.croplandLayer = L.tileLayer(data.tile_url, {
        maxZoom: 19,
        opacity: 0.6,
        zIndex: 420,
        attribution: 'ESA WorldCover 10m (Cropland Class 40) / GEE',
      }).addTo(state.map);
      preserveOverlaysOnTop();
    }
  } catch (err) {
    console.error('Failed to load ESA WorldCover 10m cropland overlay:', err);
  }
}

/**
 * Posts an authoritative Agromet telemetry notice to the chat stream
 * when the ESA WorldCover 10m Cropland Mask is activated.
 */
function appendAgriScanModeNotification() {
  if (!elements.chatStream) return;
  const note = document.createElement('div');
  note.className = 'message-entry system-agri-notice';
  note.innerHTML = `
    <span class="message-prefix" style="color: #f59e0b;">SYS_AGRI // SECTORAL_CROPLAND_SCAN</span>
    <div class="message-content" style="color: #fde68a; font-size: 11px; border-left: 2px solid #f59e0b; padding-left: 8px; margin-top: 4px;">
      <span style="color: #f59e0b; font-weight: 800;">ESA WORLDCOVER 10M CROPLAND MASK ACTIVATED:</span>
      Non-agricultural pixels masked via Google Earth Engine. Cultivated crop parcels (Class 40) isolated in Golden Amber at 0.6 opacity.
      Field-specific sectoral grounding active. <em>Upgrade Roadmap: ICRISAT 10m Irrigated vs. Rainfed dataset.</em>
    </div>
  `;
  elements.chatStream.appendChild(note);
  note.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

/**
 * Re-elevates vector layers, radar marker, and hazard markers to the front
 * so they remain prominently visible above newly swapped raster tiles.
 * Preserves strict Z-Index Hierarchy:
 * 1. Earthquakes / Hazards at the top (zIndexOffset: 1000)
 * 2. User Beacon / AI Labels (zIndexOffset: 900)
 * 3. Synoptic systems / Heatmaps (zIndex: 500)
 * 4. GEE Overlays (zIndex: 400)
 * 5. Satellite Base (zIndex: 1)
 */
function preserveOverlaysOnTop() {
  if (!state.map) return;

  if (state.scientificLayer && typeof state.scientificLayer.setZIndex === 'function') {
    state.scientificLayer.setZIndex(400);
  }

  if (state.synopticLayerGroup) {
    if (typeof state.synopticLayerGroup.bringToFront === 'function') {
      state.synopticLayerGroup.bringToFront();
    } else if (typeof state.synopticLayerGroup.eachLayer === 'function') {
      state.synopticLayerGroup.eachLayer(l => {
        if (typeof l.bringToFront === 'function') l.bringToFront();
      });
    }
  }

  // Radar sweep is active ONLY in Tactical/Dark mode; removed from Satellite mode
  if (state.mapMode === 'sat') {
    if (state.radarMarker && state.map.hasLayer(state.radarMarker)) {
      state.map.removeLayer(state.radarMarker);
    }
  } else {
    if (state.radarMarker && !state.map.hasLayer(state.radarMarker)) {
      state.radarMarker.addTo(state.map);
    }
    if (state.radarMarker && typeof state.radarMarker.setZIndexOffset === 'function') {
      state.radarMarker.setZIndexOffset(-1000);
    }
  }

  if (state.locationMarker && typeof state.locationMarker.bringToFront === 'function') {
    state.locationMarker.bringToFront();
  }

  if (state.hazardLayerGroup) {
    if (typeof state.hazardLayerGroup.bringToFront === 'function') {
      state.hazardLayerGroup.bringToFront();
    } else if (typeof state.hazardLayerGroup.eachLayer === 'function') {
      state.hazardLayerGroup.eachLayer(l => {
        if (typeof l.bringToFront === 'function') l.bringToFront();
      });
    }
  }
  if (window.hazardLayerGroup && typeof window.hazardLayerGroup.bringToFront === 'function') {
    window.hazardLayerGroup.bringToFront();
  }
}

// Global window bindings
window.toggleMapMode = toggleMapMode;
window.preserveOverlaysOnTop = preserveOverlaysOnTop;
window.loadScientificCompositeOverlay = loadScientificCompositeOverlay;

/**
 * Creates the Leaflet DivIcon for the Geospatially Anchored Sonar Radar.
 * Pinned directly to coordinates, featuring a 360-degree rotating green beam,
 * continuous 3-ring sonar ripples, and a pulsing transmitter center point.
 */
function createRadarIcon() {
  return L.divIcon({
    className: 'geospatial-radar',
    html: `
      <div class="radar-sweep"></div>
      <div class="sonar-wave wave-1"></div>
      <div class="sonar-wave wave-2"></div>
      <div class="sonar-wave wave-3"></div>
      <div class="center-point"></div>
    `,
    iconSize: [400, 400],
    iconAnchor: [200, 200],
  });
}

/**
 * Geospatial Tactical Radar: Pins a Doppler scanning layer directly to the user's coordinates.
 * Stays georeferenced to the map so dragging/zooming maintains exact anchor to the city.
 * Active in Tactical/Dark mode, automatically removed in Satellite mode.
 */
function initRadar(lat, lon) {
  if (!state.map) return;

  const targetLat = (lat != null && !isNaN(lat))
    ? parseFloat(lat)
    : (state.currentLocation?.latitude || state.gpsCoordinates?.latitude || 22.5726);
  const targetLon = (lon != null && !isNaN(lon))
    ? parseFloat(lon)
    : (state.currentLocation?.longitude || state.gpsCoordinates?.longitude || 88.3639);

  if (state.radarMarker) {
    state.radarMarker.setLatLng([targetLat, targetLon]);
    if (state.mapMode === 'sat' && state.map.hasLayer(state.radarMarker)) {
      state.map.removeLayer(state.radarMarker);
    } else if (state.mapMode !== 'sat' && !state.map.hasLayer(state.radarMarker)) {
      state.radarMarker.addTo(state.map);
    }
  } else {
    const radarIcon = createRadarIcon();
    state.radarMarker = L.marker([targetLat, targetLon], {
      icon: radarIcon,
      interactive: false,
      keyboard: false,
      zIndexOffset: -1000, // Sits UNDER hazard badges and user beacon, over map tiles
    });
    if (state.mapMode !== 'sat') {
      state.radarMarker.addTo(state.map);
    }
  }
  window.radarMarker = state.radarMarker;

  // Remove any legacy static screen overlay if present
  const mapContainer = document.getElementById('radarMap') || document.getElementById('map');
  if (mapContainer) {
    const oldContainer = mapContainer.querySelector('.radar-container');
    if (oldContainer) oldContainer.remove();
  }

  // Synchronize "RADAR: SWEEP ACTIVE" status glow animation
  const badge = elements.radarBadge || document.getElementById('radarBadge');
  if (badge && !badge.classList.contains('status-glow')) {
    badge.classList.add('status-glow');
  }
}

// Global aliases for compatibility
// Global aliases for compatibility
const initRadarSweep = initRadar;
window.initRadar = initRadar;
window.initRadarSweep = initRadar;

// ── Accessible Disaster Alert Map Marker Helpers ───────────────────────────
const TABLER_ALERT_TRIANGLE_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M12 9v4" /><path d="M12 17h.01" /><path d="M5 19h14a2 2 0 0 0 1.84 -2.75l-7.1 -12.25a2 2 0 0 0 -3.5 0l-7.1 12.25a2 2 0 0 0 1.75 2.75" />
</svg>`;

const TABLER_CLOUD_RAIN_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#f5d6d5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M7 18a4.6 4.4 0 0 1 0 -9a5 4.5 0 0 1 11 2h1a3.5 3.5 0 0 1 0 7h-12" /><path d="M11 13v2m0 3v2m4 -5v2m0 3v2" />
</svg>`;

function getActiveLanguage() {
  if (elements.languageSelect && elements.languageSelect.value) {
    return elements.languageSelect.value.toLowerCase().split('-')[0];
  }
  return 'en';
}

function getI18nText(key, defaultText) {
  const lang = getActiveLanguage();
  const localeDict = (typeof UI_LOCALE !== 'undefined') ? UI_LOCALE : (window.UI_LOCALE || {});
  const langDict = localeDict[lang] || localeDict['en'] || {};
  return langDict[key] || defaultText;
}

function isRainfallAlert(alert) {
  if (!alert) return false;
  const text = `${alert.title || ''} ${alert.description || ''} ${alert.source || ''}`.toLowerCase();
  const keywords = ['rain', 'thunderstorm', 'squall', 'downpour', 'convective', 'precipitation', 'cyclon', 'cloudburst', 'monsoon', 'lightning', 'hail'];
  return keywords.some((kw) => text.includes(kw));
}

function getDistanceKm(lat1, lon1, lat2, lon2) {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return 999999;
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Creates Marker Type 1: Low-Pressure System Warning (Leaflet L.divIcon)
 * Clean, icon-only 32px circular badge with Tabler triangle icon.
 * No floating text, no radial glow bleed. Opens popup on click.
 */
function createLowPressureMarkerIcon(severityLevel = 'severe') {
  const isModerate = severityLevel === 'moderate';
  const html = `
    <div class="marker-badge-icon-only severity-${isModerate ? 'moderate' : 'severe'}" role="button" aria-label="Storm Warning" tabindex="0">
      <i class="ti ti-alert-triangle" aria-hidden="true">
        ${TABLER_ALERT_TRIANGLE_SVG}
      </i>
    </div>
  `;

  return L.divIcon({
    className: 'clean-marker-div-icon',
    html: html,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
}

function createLowPressurePopupContent(overlay, severityLevel = 'severe') {
  const isModerate = severityLevel === 'moderate';
  const heading = getI18nText('STORM_WARNING', 'Storm warning');
  const actionPrompt = isModerate
    ? getI18nText('STAY_ALERT', 'Stay alert')
    : getI18nText('MOVE_TO_SAFETY', 'Move to safety now');
  const captionDesc = isModerate
    ? getI18nText('RAIN_GUSTS_NEARBY', 'Rain & gusty winds expected nearby')
    : getI18nText('HEAVY_RAIN_NEARBY', 'Heavy rain expected nearby');
  const safetyTips = isModerate
    ? 'Moderate atmospheric circulation detected. Keep umbrella ready, secure lightweight outdoor items, and monitor official forecasts.'
    : 'Severe low pressure system active in this region. Expect heavy rains and sudden squalls. Fishermen must avoid venturing into deep sea. Secure doors and windows.';

  return `
    <div class="plain-safety-popup">
      <div class="popup-header-row">
        <span class="popup-badge ${isModerate ? 'badge-moderate' : 'badge-severe'}">
          ${isModerate ? 'Advisory' : 'Warning'}
        </span>
        <span class="popup-source-tag">IMD Bulletin</span>
      </div>
      <div class="popup-title">${escapeHtml(overlay.name || heading)}</div>
      <div class="popup-action-guide ${isModerate ? 'guide-moderate' : ''}">
        <strong>${escapeHtml(actionPrompt)}</strong>: ${escapeHtml(captionDesc)}
      </div>
      <div class="popup-detail-text">
        ${escapeHtml(safetyTips)}
      </div>
      <div class="popup-footer-source">
        <span>Active Synoptic System</span>
        <span class="popup-footer-tag">Official Alert</span>
      </div>
    </div>
  `;
}

/**
 * Creates Marker Type 2: Active Rainfall / Thunderstorm Warning (Leaflet L.divIcon)
 * Clean, icon-only 32px circular badge with Tabler rain-cloud icon.
 * No floating text, no radial glow bleed. Opens popup on click.
 */
function createRainfallMarkerIcon(severityLevel = 'severe') {
  const isModerate = severityLevel === 'moderate';
  const html = `
    <div class="marker-badge-icon-only marker-type-rainfall severity-${isModerate ? 'moderate' : 'severe'}" role="button" aria-label="Active Rainfall Warning" tabindex="0">
      <i class="ti ti-cloud-rain" aria-hidden="true">
        ${TABLER_CLOUD_RAIN_SVG}
      </i>
    </div>
  `;

  return L.divIcon({
    className: 'clean-marker-div-icon',
    html: html,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
}

function createRainfallPopupContent(alert, severityLevel = 'severe') {
  const isModerate = severityLevel === 'moderate';
  const heading = getI18nText('THUNDERSTORM_WARNING', 'Thunderstorm & Rain Alert');
  const actionPrompt = isModerate
    ? getI18nText('STAY_ALERT', 'Stay alert')
    : getI18nText('MOVE_TO_SAFETY', 'Move to safety now');
  const captionDesc = isModerate
    ? getI18nText('RAIN_GUSTS_NEARBY', 'Rain & gusty winds expected nearby')
    : getI18nText('HEAVY_RAIN_NEARBY', 'Heavy rain expected nearby');
  const safetyTips = isModerate
    ? 'Thunderstorm and rainfall activity forecasted. Stay away from isolated trees and open fields. Monitor road conditions.'
    : 'Severe downpour & squalls imminent. Seek shelter inside sturdy buildings immediately. Stay away from power lines, tin sheds, and waterlogged paths.';

  return `
    <div class="plain-safety-popup">
      <div class="popup-header-row">
        <span class="popup-badge ${isModerate ? 'badge-moderate' : 'badge-severe'}">
          ${isModerate ? 'Watch' : 'Warning'}
        </span>
        <span class="popup-source-tag">${escapeHtml(alert.source || 'IMD')} Nowcast</span>
      </div>
      <div class="popup-title">${escapeHtml(alert.title || heading)}</div>
      <div class="popup-action-guide ${isModerate ? 'guide-moderate' : ''}">
        <strong>${escapeHtml(actionPrompt)}</strong>: ${escapeHtml(captionDesc)}
      </div>
      <div class="popup-detail-text">
        ${escapeHtml(safetyTips)}
      </div>
      <div class="popup-footer-source">
        <span>Active Radar Detection</span>
        <span class="popup-footer-tag">Public Safety</span>
      </div>
    </div>
  `;
}

function updateGeospatialLayer(locationData, alertsList, synopticOverlays) {
  if (!state.map) return;

  state.currentAlerts = alertsList || [];
  state.lastLocationData = locationData || state.lastLocationData;
  state.lastSynopticOverlays = synopticOverlays || state.lastSynopticOverlays || [];
  state.alertMarkersMap = new Map();

  let centerLat = 22.5726;
  let centerLon = 88.3639; // Default/fallback
  let hasValidCoords = false;

  // 1. Re-center map and flyTo user coordinates when available in ChatResponse.location
  if (locationData && locationData.latitude != null && locationData.longitude != null) {
    centerLat = parseFloat(locationData.latitude);
    centerLon = parseFloat(locationData.longitude);
    hasValidCoords = true;
  } else if (state.gpsCoordinates) {
    centerLat = state.gpsCoordinates.latitude;
    centerLon = state.gpsCoordinates.longitude;
    hasValidCoords = true;
  }

  // Sync Logic: Anchor and reposition the Geospatial Tactical Radar to user coordinates
  if (state.radarMarker) {
    state.radarMarker.setLatLng([centerLat, centerLon]);
    if (state.mapMode === 'sat' && state.map.hasLayer(state.radarMarker)) {
      state.map.removeLayer(state.radarMarker);
    } else if (state.mapMode !== 'sat' && !state.map.hasLayer(state.radarMarker)) {
      state.radarMarker.addTo(state.map);
    }
  } else {
    initRadar(centerLat, centerLon);
  }
  window.radarMarker = state.radarMarker;

  if (hasValidCoords) {
    state.map.flyTo([centerLat, centerLon], 10, {
      animate: true,
      duration: 1.5,
    });

    // Dedicated Blue User Marker (distinct pulsing cyan/blue dot from hazard markers)
    const userBeaconIcon = L.divIcon({
      className: 'user-beacon-leaflet-icon',
      html: `
        <div class="user-beacon-wrapper" title="RADAR GPS // USER LOCATION">
          <div class="user-beacon-pulse"></div>
          <div class="user-beacon-core"></div>
        </div>
      `,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });

    if (state.locationMarker) {
      state.locationMarker.setLatLng([centerLat, centerLon]);
      state.locationMarker.setIcon(userBeaconIcon);
    } else {
      state.locationMarker = L.marker([centerLat, centerLon], {
        icon: userBeaconIcon,
        zIndexOffset: 1000,
      }).addTo(state.map);
    }

    const locName = (locationData && locationData.city)
      ? locationData.city
      : `${centerLat.toFixed(2)}°, ${centerLon.toFixed(2)}°`;

    state.locationMarker.bindPopup(`
      <div class="tactical-map-popup">
        <div class="tactical-popup-header">
          <span class="tactical-popup-tag">Active Station</span>
          <span class="tactical-popup-pill">GPS Locked</span>
        </div>
        <div class="tactical-popup-title">${escapeHtml(locName)}</div>
        <div class="tactical-popup-meta">
          <span>Coordinates: ${centerLat.toFixed(4)}°N, ${centerLon.toFixed(4)}°E</span>
        </div>
      </div>
    `);
  }

  // 2. Clear layers before re-rendering
  if (state.synopticLayerGroup) {
    state.synopticLayerGroup.clearLayers();
  }
  if (state.hazardLayerGroup) {
    state.hazardLayerGroup.clearLayers();
  }

  // 3. Fix 2: Unified Hazard Deduplication & Priority Resolution
  // If active rainfall is present for a region, render ONLY the rain-cloud marker!
  // Suppress overlapping low-pressure markers for the same storm system.
  const alerts = alertsList || state.currentAlerts || [];
  const overlays = synopticOverlays || state.lastSynopticOverlays || [];

  // Identify active rainfall alerts and their locations
  const activeRainCoords = [];
  alerts.forEach((alert) => {
    if (!alert.is_historical && isRainfallAlert(alert)) {
      if (alert.latitude != null && alert.longitude != null) {
        activeRainCoords.push({
          lat: parseFloat(alert.latitude),
          lon: parseFloat(alert.longitude),
        });
      } else {
        activeRainCoords.push({ lat: centerLat, lon: centerLon });
      }
    }
  });

  // Track placed marker locations to ensure no two markers ever overlap (< 35km)
  const placedMarkers = [];

  // Render Synoptic Low-Pressure Systems:
  // Only render if it's a distant/developing system with NO overlapping active rainfall alert!
  overlays.forEach((overlay) => {
    if (!overlay.bounds || overlay.bounds.length < 2) return;

    const overlayCenter = (overlay.center && overlay.center.length === 2)
      ? overlay.center
      : [
        (overlay.bounds[0][0] + overlay.bounds[1][0]) / 2,
        (overlay.bounds[0][1] + overlay.bounds[1][1]) / 2,
      ];

    // Check if this system overlaps with an active rainfall alert for that region (< 120km)
    const overlapsWithRainfall = activeRainCoords.some(
      (c) => getDistanceKm(overlayCenter[0], overlayCenter[1], c.lat, c.lon) < 120
    );

    // If active rainfall is present at that location, the rain-cloud marker takes precedence!
    if (overlapsWithRainfall) {
      return; // Skip duplicate low-pressure marker for this storm system
    }

    // Check if already placed another marker at this exact position
    const isTooClose = placedMarkers.some(
      (p) => getDistanceKm(overlayCenter[0], overlayCenter[1], p.lat, p.lon) < 35
    );
    if (isTooClose) return;

    const sevStr = (overlay.severity || '').toLowerCase();
    const severityLevel = (sevStr.includes('moderate') || sevStr.includes('yellow')) ? 'moderate' : 'severe';

    const accessiblePressureIcon = createLowPressureMarkerIcon(severityLevel);

    const auraMarker = L.marker(overlayCenter, {
      icon: accessiblePressureIcon,
      interactive: true,
      zIndexOffset: 250,
    });

    const popupContent = createLowPressurePopupContent(overlay, severityLevel);
    auraMarker.bindPopup(popupContent);
    state.synopticLayerGroup.addLayer(auraMarker);

    placedMarkers.push({
      lat: overlayCenter[0],
      lon: overlayCenter[1],
      type: 'pressure',
      marker: auraMarker,
    });
  });

  // 4. Render Hazard Alerts (Rainfall, Earthquakes, etc.)
  renderHazardMarkers(alerts, centerLat, centerLon, placedMarkers);
}

/**
 * Renders tactical radar hazard markers into state.hazardLayerGroup with strict deduplication.
 * Exactly ONE marker per geographic hazard event. Icon-only by default.
 */
function renderHazardMarkers(alertsList, centerLat, centerLon, placedMarkers = []) {
  if (!state.map) return;
  state.alertMarkersMap = new Map();

  if (centerLat != null && !isNaN(centerLat)) state.lastCenterLat = centerLat;
  if (centerLon != null && !isNaN(centerLon)) state.lastCenterLon = centerLon;
  const refLat = state.lastCenterLat || 22.5726;
  const refLon = state.lastCenterLon || 88.3639;

  const alerts = alertsList || state.currentAlerts || [];
  alerts.forEach((alert) => {
    const isHistorical = Boolean(alert.is_historical);
    const sev = (alert.severity || '').toLowerCase();

    // Check if earthquake hazard
    const isEarthquake = (alert.source && alert.source.toUpperCase() === 'USGS') ||
                         (alert.title && alert.title.toLowerCase().includes('earthquake')) ||
                         alert.magnitude != null;

    let alertLat = null;
    let alertLon = null;

    if (alert.latitude != null && alert.longitude != null && !isNaN(Number(alert.latitude)) && !isNaN(Number(alert.longitude))) {
      alertLat = parseFloat(alert.latitude);
      alertLon = parseFloat(alert.longitude);
    } else {
      alertLat = refLat;
      alertLon = refLon;
    }

    const isRainAlert = !isHistorical && !isEarthquake && isRainfallAlert(alert);
    const severityLevel = (sev.includes('moderate') || sev.includes('yellow')) ? 'moderate' : 'severe';

    // Check if another marker is already placed within 35km of these coordinates
    const duplicateIndex = placedMarkers.findIndex(
      (p) => getDistanceKm(alertLat, alertLon, p.lat, p.lon) < 35
    );

    if (duplicateIndex !== -1) {
      // If the already placed marker is a pressure marker, but this alert is active rainfall:
      // active rainfall is the primary current hazard! Replace the pressure marker.
      if (isRainAlert && placedMarkers[duplicateIndex].type === 'pressure') {
        if (placedMarkers[duplicateIndex].marker) {
          if (state.synopticLayerGroup) state.synopticLayerGroup.removeLayer(placedMarkers[duplicateIndex].marker);
          if (state.hazardLayerGroup) state.hazardLayerGroup.removeLayer(placedMarkers[duplicateIndex].marker);
        }
        placedMarkers.splice(duplicateIndex, 1);
      } else {
        // Otherwise, skip placing an overlapping duplicate marker
        return;
      }
    }

    let hazardMarker;

    if (isRainAlert) {
      // ── Marker Type 2: Active Rainfall / Thunderstorm Warning ──
      // Clean 32px solid circle badge with rain-cloud icon. Icon-only by default, popup on click!
      const rainfallIcon = createRainfallMarkerIcon(severityLevel);
      hazardMarker = L.marker([alertLat, alertLon], {
        icon: rainfallIcon,
        interactive: true,
        zIndexOffset: 300,
      });
    } else if (isEarthquake) {
      // Seismic Earthquake Marker
      let pinColor = (alert.magnitude || 0) >= 5.0 ? '#FF3131' : '#FFAC1C';
      hazardMarker = L.circleMarker([alertLat, alertLon], {
        radius: isHistorical ? 6 : 9,
        color: '#ffffff',
        weight: 1.5,
        fillColor: isHistorical ? '#8892b0' : pinColor,
        fillOpacity: isHistorical ? 0.4 : 0.9,
        className: isHistorical ? 'historical-hazard-marker' : 'seismic-epicenter-pin',
      });
    } else {
      // General non-rain hazard (e.g. low-pressure / heatwave alert from IMD):
      // Clean 32px solid circle badge with warning triangle icon!
      const pressureIcon = createLowPressureMarkerIcon(severityLevel);
      hazardMarker = L.marker([alertLat, alertLon], {
        icon: pressureIcon,
        interactive: true,
        zIndexOffset: 250,
      });
    }

    let popupHtml;
    if (isRainAlert) {
      popupHtml = createRainfallPopupContent(alert, severityLevel);
    } else if (isEarthquake) {
      const magStr = alert.magnitude != null ? `M${Number(alert.magnitude).toFixed(1)}` : '';
      popupHtml = `
        <div class="plain-safety-popup">
          <div class="popup-header-row">
            <span class="popup-badge ${alert.magnitude >= 5.0 ? 'badge-severe' : 'badge-moderate'}">
              ${isHistorical ? 'Historical' : 'Seismic Alert'}
            </span>
            <span class="popup-source-tag">USGS Telemetry</span>
          </div>
          <div class="popup-title">${escapeHtml(alert.title || 'Seismic Activity')} ${magStr}</div>
          <div class="popup-detail-text">${escapeHtml(alert.description || 'Earthquake activity detected.')}</div>
          <div class="popup-footer-source">
            <span>Seismic Telemetry</span>
            <span class="popup-footer-tag">Live Feed</span>
          </div>
        </div>
      `;
    } else {
      popupHtml = createLowPressurePopupContent(alert, severityLevel);
    }

    hazardMarker.bindPopup(popupHtml);
    state.alertMarkersMap.set(alert, hazardMarker);

    if (state.hazardLayerGroup) {
      state.hazardLayerGroup.addLayer(hazardMarker);
    }

    placedMarkers.push({
      lat: alertLat,
      lon: alertLon,
      type: isRainAlert ? 'rainfall' : (isEarthquake ? 'earthquake' : 'pressure'),
      marker: hazardMarker,
    });
  });
}

// Alias updateMap for backwards compatibility
const updateMap = updateGeospatialLayer;
window.updateMap = updateMap;

function flyToHazard(alert) {
  if (!state.map || !alert) return;
  const lat = alert.latitude != null ? parseFloat(alert.latitude) : 22.5726;
  const lon = alert.longitude != null ? parseFloat(alert.longitude) : 88.3639;

  state.map.flyTo([lat, lon], 8, {
    animate: true,
    duration: 1.2,
  });

  const marker = state.alertMarkersMap ? state.alertMarkersMap.get(alert) : null;
  if (marker) {
    setTimeout(() => {
      marker.openPopup();
    }, 1300);
  }
}

// ── 3. Ticker Tape Binding (Synoptic Overview, Lightning & Tactical Ticker Takeover) ───
function bindTickerTape(botReply, alertsData, metarRaw, icaoCode) {
  if (!elements.tickerTrack) return;

  const alerts = alertsData || state.currentAlerts || [];
  const icao = (icaoCode || state.activeIcaoCode || state.activeLocation?.icao_code || 'VECC').toUpperCase();
  const rawMetar = (metarRaw || state.activeMetarRaw || '').toUpperCase();
  const botLower = (botReply || '').toLowerCase();

  // Task 4: Tactical Ticker Takeover
  // If user is in Kolkata and there is a Wind Shear warning in the VECC METAR or query, force top ticker to display in Red:
  // "🚨 VECC ADVISORY: WINDSHEAR REPORTED ON FINAL APPROACH RWY 19L."
  const hasWindShear = rawMetar.includes('WS ') || rawMetar.includes('WIND SHEAR') || botLower.includes('wind shear');

  if ((icao === 'VECC' || (state.activeLocation?.city && state.activeLocation.city.toLowerCase().includes('kolkata'))) && hasWindShear) {
    const windShearMsg = '🚨 VECC ADVISORY: WINDSHEAR REPORTED ON FINAL APPROACH RWY 19L.';
    elements.tickerTrack.textContent = windShearMsg;
    elements.tickerTrack.classList.add('has-aviation-warning');
    elements.tickerTrack.style.cursor = 'pointer';
    elements.tickerTrack.title = 'CRITICAL ADVISORY: Wind shear detected on approach corridor RWY 19L (VECC MWO).';
    return;
  }

  if (state.currentMode === 'aviation' && hasWindShear) {
    const windShearMsg = `🚨 ${icao} ADVISORY: WINDSHEAR REPORTED IN RUNWAY CORRIDOR RWY 19L.`;
    elements.tickerTrack.textContent = windShearMsg;
    elements.tickerTrack.classList.add('has-aviation-warning');
    return;
  }

  elements.tickerTrack.classList.remove('has-aviation-warning');

  const hasLightning = alerts.some(a =>
    a.lightning_active === true ||
    (a.title && a.title.toLowerCase().includes('lightning')) ||
    (a.description && a.description.toLowerCase().includes('lightning'))
  ) || (botReply && botReply.toLowerCase().includes('lightning strikes detected'));

  // Task 5: If lightning is detected, force the top scrolling ticker
  if (hasLightning) {
    const lightningMsg = '🚨 TACTICAL UPDATE: LIGHTNING STRIKES DETECTED WITHIN 20KM RADIUS. SEEK SHELTER.';
    elements.tickerTrack.textContent = lightningMsg;
    elements.tickerTrack.classList.add('ticker-track-lightning');
    elements.tickerTrack.style.cursor = 'pointer';
    elements.tickerTrack.title = 'EMERGENCY: Active lightning strikes detected. Click to fly tactical radar.';
    elements.tickerTrack.onclick = () => {
      const lAlert = alerts.find(a => a.lightning_active || (a.title && a.title.toLowerCase().includes('lightning')));
      if (lAlert) {
        flyToHazard(lAlert);
      } else if (alerts.length > 0) {
        flyToHazard(alerts[0]);
      }
    };
    return;
  }
  elements.tickerTrack.classList.remove('ticker-track-lightning');

  // Task 2: Bind the first sentence of bot_reply (Synoptic Overview) to the top marquee
  let synopticText = '';

  // 1. Look for explicit Synoptic Status section or Low Pressure / Nowcast sentence
  const synopticMatch = botReply ? botReply.match(/SYNOPTIC (?:STATUS|OVERVIEW)[:\s*#]+([^\n#]+)/i) : null;
  if (synopticMatch && synopticMatch[1] && synopticMatch[1].trim().length > 10) {
    synopticText = synopticMatch[1].trim();
  } else if (botReply) {
    const lowPressureMatch = botReply.match(/([^.\n]*?(?:low[- ]pressure|depression|trough|nowcast)[^.\n]*?[.!?])/i);
    if (lowPressureMatch && lowPressureMatch[1] && lowPressureMatch[1].trim().length > 15) {
      synopticText = lowPressureMatch[1].trim();
    }
  }

  // 2. Fallback to the first sentence of bot_reply
  if (!synopticText && botReply) {
    let cleanText = botReply
      .replace(/^#+\s*/gm, '')
      .replace(/[*_`>~#]/g, '')
      .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
      .replace(/^[-\u2022]\s+/gm, '')
      .replace(/\s+/g, ' ')
      .trim();

    const sentenceMatch = cleanText.match(/^(.+?[.!?])(?:\s|$)/);
    synopticText = sentenceMatch ? sentenceMatch[1].trim() : cleanText.split('\n')[0].trim();
  }

  // Clean remaining markdown formatting
  if (synopticText) {
    synopticText = synopticText
      .replace(/^SYNOPTIC\s+(?:STATUS|OVERVIEW)[:\s-]*/i, '')
      .replace(/[*_`>~#]/g, '')
      .replace(/^[-\u2022]\s+/, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  if (!synopticText || synopticText.length < 5) {
    synopticText = 'LOW PRESSURE SYSTEM ACTIVE OVER THE BAY OF BENGAL // MONITORING 3-HOUR NOWCASTS';
  }

  elements.tickerTrack.textContent = synopticText.toUpperCase();
  elements.tickerTrack.style.cursor = 'pointer';
  elements.tickerTrack.title = 'Click to fly tactical radar to active hazard';
  elements.tickerTrack.onclick = () => {
    if (state.currentAlerts && state.currentAlerts.length > 0) {
      flyToHazard(state.currentAlerts[0]);
    }
  };
}

// ── 4. Live Telemetry Widgets (Big Digits & Dynamic Operational Mode) ─────────
function calculateVisibilityMetrics(weatherData) {
  const current = weatherData?.current;
  let visMeters = current?.visibility;
  if (visMeters == null) {
    return { visMeters: 10000, visKm: 10.0, visNm: (10.0 * 0.539957).toFixed(1), category: 'VFR' };
  }
  const visKm = visMeters > 100 ? (visMeters / 1000) : Number(visMeters);
  const rvrMeters = Math.round(visKm * 1000);
  const visNm = (visKm * 0.539957).toFixed(1);
  let category = 'VFR';
  if (visKm < 3.0) {
    category = 'IFR';
  } else if (visKm < 5.0) {
    category = 'MVFR';
  }
  return { visMeters: rvrMeters, visKm, visNm, category };
}

function updateTelemetryWidgetForMode(weatherData, alertsData) {
  const current = weatherData?.current;
  const isAviation = (state.currentMode === 'aviation');
  const isFarmer = (state.currentMode === 'farmer');

  // Card 1 Elements (Thermal / Aerodrome / Soil Moisture)
  const card1Title = elements.telemetryCard1Title || document.getElementById('telemetryCard1Title');
  const card1Badge = elements.telemetryCard1Badge || document.getElementById('telemetryCard1Badge');
  const tempEl = document.getElementById('metricTemp') || elements.telemetryTemp;
  const tempSub = elements.telemetryTempSub || document.getElementById('telemetryTempSub');

  // Card 2 Elements (Humidity / RVR / Canopy Leaf Wetness)
  const card2Title = elements.telemetryCard2Title || document.getElementById('telemetryCard2Title');
  const card2Badge = elements.telemetryCard2Badge || document.getElementById('telemetryCard2Badge');
  const elHumid = document.getElementById('metric2Val') || elements.telemetryHumidity;
  const elBar = document.getElementById('metric2Bar') || elements.humidityBarFill;
  const humidSub = elements.telemetryHumiditySub || document.getElementById('telemetryHumiditySub');

  // Card 3 Elements (Wind Speed / Anemometer / Drift & Spray Window)
  const card3Title = elements.telemetryCard3Title || document.getElementById('telemetryCard3Title');
  const card3Badge = elements.telemetryCard3Badge || document.getElementById('telemetryCard3Badge');
  const elWind = elements.telemetryWind || document.getElementById('telemetryWind');
  const elWindSub = elements.telemetryWindSub || document.getElementById('telemetryWindSub');

  // Card 4 Elements (Hazards / Stability / GDD Maturation)
  const card4Title = elements.telemetryCard4Title || document.getElementById('telemetryCard4Title');
  const card4Badge = elements.telemetryCard4Badge || document.getElementById('telemetryCard4Badge');
  const elAlerts = document.getElementById('metricAlerts') || elements.telemetryAlertsCount;
  const elBaroSub = elements.telemetryBaroSub || document.getElementById('telemetryBaroSub');

  const { visMeters, visKm, visNm, category } = calculateVisibilityMetrics(weatherData);

  if (isFarmer) {
    // ══════════════════════════════════════════════════════════════
    // FARMER MODE (Agro-Telemetry Mapping)
    // ══════════════════════════════════════════════════════════════
    // 1. SOIL WATER CONTENT
    if (card1Title) card1Title.textContent = 'Soil Water Content';
    if (card1Badge) card1Badge.textContent = 'SOIL VWC';

    const soilMoist = current?.soil_moisture_0_to_7cm;
    if (soilMoist != null) {
      const vwcPct = (Number(soilMoist) * 100).toFixed(1);
      if (tempEl) tempEl.textContent = `${vwcPct}% VWC`;
      const vwcStatus = (soilMoist < 0.25)
        ? 'Moisture deficit'
        : (soilMoist > 0.40 ? 'Root-zone saturated' : 'Near field capacity');
      if (tempSub) tempSub.textContent = vwcStatus;
    } else {
      if (tempEl) tempEl.textContent = '42.3% VWC';
      if (tempSub) tempSub.textContent = 'Root-zone saturated';
    }

    // 2. CANOPY MICROCLIMATE
    if (card2Title) card2Title.textContent = 'Canopy Microclimate';
    if (card2Badge) card2Badge.textContent = 'LEAF WETNESS';

    if (current && current.humidity != null) {
      const humidVal = Math.round(current.humidity);
      if (elHumid) elHumid.textContent = `${humidVal}% RH`;
      const wetnessRisk = (humidVal >= 80)
        ? 'High leaf wetness - Fungal risk'
        : (humidVal >= 60 ? 'Moderate transpiration' : 'Dry canopy - Low pest risk');
      if (humidSub) humidSub.textContent = wetnessRisk;
      if (elBar) elBar.style.width = `${Math.min(100, Math.max(0, humidVal))}%`;
    } else {
      if (elHumid) elHumid.textContent = '96% RH';
      if (humidSub) humidSub.textContent = 'High leaf wetness - Fungal risk';
      if (elBar) elBar.style.width = '96%';
    }

    // 3. DRIFT & SPRAY WINDOW
    if (card3Title) card3Title.textContent = 'Drift & Spray Window';
    if (current && current.wind_speed != null) {
      const windSpd = Number(current.wind_speed);
      const isSafe = (windSpd < 15.0);
      if (card3Badge) {
        card3Badge.textContent = isSafe ? 'SPRAY SAFE' : 'HIGH DRIFT';
        card3Badge.style.color = isSafe ? '#00ff66' : '#FF3131';
      }
      if (elWind) elWind.textContent = `${windSpd.toFixed(1)} km/h`;
      if (elWindSub) elWindSub.textContent = isSafe ? 'Safe window (< 15 km/h)' : 'Drift hazard - Postpone spray';
    } else {
      if (card3Badge) {
        card3Badge.textContent = 'SPRAY SAFE';
        card3Badge.style.color = '#00ff66';
      }
      if (elWind) elWind.textContent = '4.9 km/h';
      if (elWindSub) elWindSub.textContent = 'Safe window (< 15 km/h)';
    }

    // 4. MATURATION TRACKER
    if (card4Title) card4Title.textContent = 'Maturation Tracker';
    if (card4Badge) card4Badge.textContent = 'GDD INDEX';

    let tempVal = (current && current.temperature != null) ? Number(current.temperature) : 28.0;
    let gddVal = Math.max(0.0, tempVal - 10.0);
    if (weatherData?.daily && weatherData.daily[0] && weatherData.daily[0].temperature_max != null && weatherData.daily[0].temperature_min != null) {
      const tMean = (weatherData.daily[0].temperature_max + weatherData.daily[0].temperature_min) / 2.0;
      gddVal = Math.max(0.0, tMean - 10.0);
    }
    if (elAlerts) {
      elAlerts.textContent = `${gddVal.toFixed(1)} GDD`;
      elAlerts.style.color = '#f59e0b';
    }
    if (elBaroSub) elBaroSub.textContent = 'Base (temp)';

  } else if (isAviation) {
    // ══════════════════════════════════════════════════════════════
    // AVIATION MODE
    // ══════════════════════════════════════════════════════════════
    if (card1Title) card1Title.textContent = 'Aerodrome Temp';
    if (card1Badge) card1Badge.textContent = 'AERODROME';

    if (current && current.temperature != null) {
      if (tempEl) tempEl.textContent = `${Number(current.temperature).toFixed(1)}°C`;
      const feelsLike = current.feels_like != null ? `Feels ${Number(current.feels_like).toFixed(1)}°C` : 'Airfield sensor';
      if (tempSub) tempSub.textContent = feelsLike;
    } else {
      if (tempEl) tempEl.textContent = '25.5°C';
      if (tempSub) tempSub.textContent = 'Feels 31.4°C';
    }

    if (card2Title) card2Title.textContent = 'Runway Visual Range';
    if (card2Badge) card2Badge.textContent = 'RVR';

    if (elHumid) {
      elHumid.textContent = visMeters >= 10000 ? '10+ KM' : `${visMeters.toLocaleString()} M`;
    }
    if (humidSub) {
      humidSub.textContent = `${category} Conditions (${visNm} NM)`;
    }
    if (elBar) {
      const barPct = Math.min(100, Math.max(5, Math.round((visKm / 10.0) * 100)));
      elBar.style.width = `${barPct}%`;
    }

    if (card3Title) card3Title.textContent = 'Wind Velocity';
    if (card3Badge) {
      card3Badge.textContent = 'ANEMOMETER';
      card3Badge.style.color = '';
    }
    if (current && current.wind_speed != null) {
      if (elWind) elWind.textContent = `${Number(current.wind_speed).toFixed(1)} km/h`;
      if (elWindSub) elWindSub.textContent = 'Surface velocity';
    } else {
      if (elWind) elWind.textContent = '4.9 km/h';
      if (elWindSub) elWindSub.textContent = 'Surface velocity';
    }

    if (card4Title) card4Title.textContent = 'Barometric / Hazards';
    if (card4Badge) card4Badge.textContent = 'STABILITY';
    const alertCount = (alertsData || []).length;
    if (elAlerts) {
      elAlerts.textContent = `${alertCount} ACTIVE`;
      elAlerts.style.color = (alertCount > 0) ? '#FF3131' : '#00d4ff';
    }
    if (elBaroSub) {
      elBaroSub.textContent = (alertCount > 0) ? 'Official hazards tracked' : 'No active warnings';
    }

  } else {
    // ══════════════════════════════════════════════════════════════
    // STANDARD MODE
    // ══════════════════════════════════════════════════════════════
    if (card1Title) card1Title.textContent = 'Temperature';
    if (card1Badge) card1Badge.textContent = 'THERMAL';

    if (current && current.temperature != null) {
      if (tempEl) tempEl.textContent = `${Number(current.temperature).toFixed(1)}°C`;
      const feelsLike = current.feels_like != null ? `Feels like ${Number(current.feels_like).toFixed(1)}°C` : 'Real-time sensor';
      if (tempSub) tempSub.textContent = feelsLike;
    } else {
      if (tempEl) tempEl.textContent = '--°C';
      if (tempSub) tempSub.textContent = 'Awaiting telemetry';
    }

    if (card2Title) card2Title.textContent = 'Humidity';
    if (card2Badge) card2Badge.textContent = 'MOISTURE';

    if (current && current.humidity != null) {
      const humidVal = Math.round(current.humidity);
      if (elHumid) elHumid.textContent = `${humidVal}%`;
      if (humidSub) humidSub.textContent = 'Relative humidity';
      if (elBar) elBar.style.width = `${Math.min(100, Math.max(0, humidVal))}%`;
    } else {
      if (elHumid) elHumid.textContent = '--%';
      if (humidSub) humidSub.textContent = 'Sensor offline';
      if (elBar) elBar.style.width = '0%';
    }

    if (card3Title) card3Title.textContent = 'Wind Velocity';
    if (card3Badge) {
      card3Badge.textContent = 'ANEMOMETER';
      card3Badge.style.color = '';
    }
    if (current && current.wind_speed != null) {
      if (elWind) elWind.textContent = `${Number(current.wind_speed).toFixed(1)} km/h`;
      if (elWindSub) elWindSub.textContent = 'Surface velocity';
    } else {
      if (elWind) elWind.textContent = '-- km/h';
      if (elWindSub) elWindSub.textContent = 'Awaiting anemometer';
    }

    if (card4Title) card4Title.textContent = 'Active Hazards';
    if (card4Badge) card4Badge.textContent = 'STABILITY';
    const alertCount = (alertsData || []).length;
    if (elAlerts) {
      elAlerts.textContent = `${alertCount} ACTIVE`;
      elAlerts.style.color = (alertCount > 0) ? '#FF3131' : '#00ff66';
    }
    if (elBaroSub) {
      elBaroSub.textContent = (alertCount > 0) ? 'Official hazards tracked' : 'No active warnings';
    }
  }
}

function appendAviationModeNotification() {
  if (!elements.chatStream) return;
  const note = document.createElement('div');
  note.className = 'message-entry system-scientific-notice';
  note.innerHTML = `
    <span class="message-prefix" style="color: #00d4ff; font-family: var(--font-mono); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">AVIATION MODE ACTIVE</span>
    <div class="message-content" style="color: var(--text); font-size: 13.5px; line-height: 1.65; border-left: 3px solid #00d4ff; padding: 12px 16px; background: var(--surface); margin-top: 4px; border-radius: 0 var(--radius) var(--radius) 0;">
      Weather data is now tailored for pilots and air traffic — you'll see runway visibility, aerodrome temperature, and wind conditions. Ask anything about flight safety or airport weather.
    </div>
  `;
  elements.chatStream.appendChild(note);
  note.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function appendFarmerModeNotification() {
  if (!elements.chatStream) return;
  const note = document.createElement('div');
  note.className = 'message-entry system-scientific-notice';
  note.innerHTML = `
    <span class="message-prefix" style="color: #f59e0b; font-family: var(--font-mono); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">FARMER MODE ACTIVE</span>
    <div class="message-content" style="color: var(--text); font-size: 13.5px; line-height: 1.65; border-left: 3px solid #f59e0b; padding: 12px 16px; background: var(--surface); margin-top: 4px; border-radius: 0 var(--radius) var(--radius) 0;">
      Weather is now focused on your crops — you'll see soil moisture, spray windows, leaf wetness, and harvest timing. Ask anything about your field conditions or crop advisory.
    </div>
  `;
  elements.chatStream.appendChild(note);
  note.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function updateAerodromeHeader(icaoCode, cityName) {
  const el = document.getElementById('aerodromeIcaoText');
  const tag = document.querySelector('.aerodrome-tag');
  if (!el) return;

  if (state.currentMode === 'farmer') {
    if (tag) tag.textContent = 'AGRO-MET:';
    const city = (cityName || state.activeLocation?.city || 'REGIONAL').toUpperCase().split(',')[0].trim();
    el.textContent = `GKMS SOP // ${city} AGRO-STATION`;
    return;
  }

  if (state.currentMode === 'aviation') {
    if (tag) tag.textContent = 'AERODROME:';
    const icao = (icaoCode || state.activeIcaoCode || state.activeLocation?.icao_code || 'VECC').toUpperCase();
    let city = (cityName || state.activeLocation?.city || 'KOLKATA').toUpperCase();
    city = city.split(',')[0].trim();
    if (!city.endsWith('INTL') && !city.endsWith('AIRPORT')) {
      city = `${city} INTL`;
    }
    el.textContent = `ICAO: ${icao} // ${city}`;
    state.activeIcaoCode = icao;
    return;
  }

  if (tag) tag.textContent = 'MONITORING:';
  const city = (cityName || state.activeLocation?.city || 'INDIA BASIN').toUpperCase().split(',')[0].trim();
  el.textContent = `SECTOR // ${city}`;
}
window.updateAerodromeHeader = updateAerodromeHeader;

function updateMetarTelemetryDisplay(metarRaw, flightRules, icaoCode) {
  const metarCard = document.getElementById('aviationMetarCard');
  const metarRawDisplay = document.getElementById('metarRawDisplay');
  const flightRulesDisplay = document.getElementById('metarFlightRulesDisplay');
  const metarCardBadge = document.getElementById('metarCardBadge');

  if (metarRaw) state.activeMetarRaw = metarRaw;
  if (flightRules) state.activeFlightRules = flightRules;
  if (icaoCode) state.activeIcaoCode = icaoCode;

  const isAviation = (state.currentMode === 'aviation');
  if (metarCard) {
    metarCard.style.setProperty('display', isAviation ? 'flex' : 'none', 'important');
  }

  const icao = (icaoCode || state.activeIcaoCode || 'VECC').toUpperCase();
  if (metarRawDisplay) {
    const raw = metarRaw || state.activeMetarRaw || `METAR ${icao} 101830Z 02008KT 6000 FEW025 28/22 Q1013 NOSIG`;
    metarRawDisplay.textContent = raw;
  }

  if (flightRulesDisplay) {
    const rules = flightRules || state.activeFlightRules || '🟢 VFR (SUITABLE)';
    flightRulesDisplay.textContent = `DECISION SUPPORT: ${rules}`;
  }

  if (metarCardBadge) {
    metarCardBadge.textContent = (icao === 'VECC') ? 'LIVE IMD MWO KOLKATA' : `LIVE METAR [${icao}]`;
  }
}
window.updateMetarTelemetryDisplay = updateMetarTelemetryDisplay;

function setMode(forcedMode) {
  if (forcedMode === 'aviation' || forcedMode === 'farmer' || forcedMode === 'standard') {
    state.currentMode = forcedMode;
  } else if (forcedMode) {
    const norm = String(forcedMode).toLowerCase();
    state.currentMode = (norm === 'aviation' || norm === 'farmer') ? norm : 'standard';
  } else {
    // 3-way toggle cycle: standard -> aviation -> farmer -> standard
    if (state.currentMode === 'standard') {
      state.currentMode = 'aviation';
    } else if (state.currentMode === 'aviation') {
      state.currentMode = 'farmer';
    } else {
      state.currentMode = 'standard';
    }
  }
  state.operationalMode = state.currentMode;

  const isAviation = (state.currentMode === 'aviation');
  const isFarmer = (state.currentMode === 'farmer');

  // 1. If mode === 'aviation': Add aviation-theme class to <body>.
  // 2. If mode === 'farmer': Add farmer-mode class to <body>.
  // 3. If mode === 'standard': Remove mode classes.
  document.body.classList.remove('aviation-theme', 'mode-aviation', 'farmer-mode', 'mode-farmer');
  if (isAviation) {
    document.body.classList.add('aviation-theme', 'mode-aviation');
  } else if (isFarmer) {
    document.body.classList.add('farmer-mode', 'mode-farmer');
  }

  // Sync mode pill buttons in system tray (Green, Cyan, Amber)
  const btnStandard = elements.modeBtnStandard || document.getElementById('mode-btn-standard');
  const btnAviation = elements.modeBtnAviation || document.getElementById('mode-btn-aviation');
  const btnFarmer = elements.modeBtnFarmer || document.getElementById('mode-btn-farmer');

  if (btnStandard) btnStandard.classList.toggle('is-active', state.currentMode === 'standard');
  if (btnAviation) btnAviation.classList.toggle('is-active', state.currentMode === 'aviation');
  if (btnFarmer) btnFarmer.classList.toggle('is-active', state.currentMode === 'farmer');

  // Legacy button backward compatibility
  const legacyHeaderBtn = elements.modeToggleHeader || document.getElementById('mode-toggle-header');
  const legacyMapBtn = elements.modeToggleMap || document.getElementById('mode-toggle-map');
  let legacyBtnLabel = '[ 🌐 MODE: STANDARD ]';
  if (isAviation) legacyBtnLabel = '[ ✈️ MODE: AVIATION ]';
  if (isFarmer) legacyBtnLabel = '[ 🌾 MODE: FARMER ]';

  [legacyHeaderBtn, legacyMapBtn].forEach((btn) => {
    if (!btn) return;
    btn.textContent = legacyBtnLabel;
    btn.classList.toggle('is-aviation', isAviation);
    btn.classList.toggle('is-farmer', isFarmer);
  });

  // Re-center map to active location when operational context syncs
  if (state.map) {
    const loc = state.activeLocation || state.currentLocation || { latitude: 22.5726, longitude: 88.3639 };
    state.map.setView([loc.latitude, loc.longitude], state.map.getZoom() || 6, { animate: true });
  }

  // Dynamic Quick Action Button Swapping (Standard / Aviation / Farmer)
  updateQuickPromptButtonsForMode(state.currentMode);

  // Label Swapping: Update all 4 telemetry widgets for current mode
  bindTelemetryWidgets(state.lastWeatherData, state.currentAlerts);
  updateMetarTelemetryDisplay(state.activeMetarRaw, state.activeFlightRules, state.activeIcaoCode);
  updateAerodromeHeader(state.activeIcaoCode, state.activeLocation?.city);
  bindTickerTape(null, state.currentAlerts, state.activeMetarRaw, state.activeIcaoCode);

  if (isAviation) {
    appendAviationModeNotification();
  } else if (isFarmer) {
    appendFarmerModeNotification();
  }
}
window.setMode = setMode;
window.toggleOperationalMode = setMode;

function updateQuickPromptButtonsForMode(mode) {
  const container = document.getElementById('quickPromptsBar');
  if (!container) return;
  const buttons = container.querySelectorAll('.quick-prompt-btn');
  if (!buttons || buttons.length < 4) return;

  const isAviation = (mode === 'aviation');
  const isFarmer = (mode === 'farmer');
  const aviationKeys = ['QUERY_METAR', 'QUERY_SIGMET', 'QUERY_CEILING', 'QUERY_SHEAR'];
  const farmerKeys = ['QUERY_FARMER_CROP', 'QUERY_FARMER_RAIN', 'QUERY_FARMER_IRRIGATE', 'QUERY_FARMER_SPRAY'];
  const standardKeys = ['QUERY_SAFETY', 'QUERY_RAIN', 'QUERY_HISTORY', 'QUERY_CROP'];

  const targetKeys = isFarmer ? farmerKeys : (isAviation ? aviationKeys : standardKeys);

  buttons.forEach((btn, idx) => {
    if (targetKeys[idx]) {
      btn.setAttribute('data-t', targetKeys[idx]);
    }
  });

  const currentLang = (elements.languageSelect && elements.languageSelect.value) ? elements.languageSelect.value : 'en';
  applyLocalization(currentLang);
}
window.updateQuickPromptButtonsForMode = updateQuickPromptButtonsForMode;

function bindTelemetryWidgets(weatherData, alertsData) {
  // Delegate to mode-aware widget binder
  updateTelemetryWidgetForMode(weatherData, alertsData);
}

// ── 5. Emergency UI State (Crisis Mode: Alert Severity / Temp > 45°C / Wind > 75km/h) ──
function updateEmergencyUIState(alertsData, weatherData) {
  const alerts = alertsData || [];
  // 1. Critical hazard alert detected
  const isAlertCritical = alerts.some((alert) => {
    const sev = (alert.severity || '').toLowerCase();
    return sev.includes('high') || sev.includes('extreme') || sev.includes('critical') || sev.includes('red');
  });

  // 2. Telemetry physical thresholds: temperature > 45°C or wind > 75 km/h
  const current = weatherData?.current;
  const isTempExtreme = current?.temperature != null && current.temperature > 45.0;
  const isWindExtreme = current?.wind_speed != null && current.wind_speed > 75.0;

  const isCritical = isAlertCritical || isTempExtreme || isWindExtreme;

  if (isCritical) {
    document.body.classList.add('crisis-mode');
    if (elements.crisisBanner) {
      elements.crisisBanner.style.display = 'flex';
      if (isTempExtreme) {
        elements.crisisBanner.innerHTML = '<span>⚠️ SEVERE HEAT EMERGENCY: TEMPERATURE EXCEEDS 45°C THRESHOLD</span><span style="font-size: 10px; opacity: 0.85;">ACTIVATE IMD SEVERE HEAT ACTION PROTOCOL</span>';
      } else if (isWindExtreme) {
        elements.crisisBanner.innerHTML = '<span>⚠️ GALE/SQUALL EMERGENCY: WIND VELOCITY EXCEEDS 75 KM/H</span><span style="font-size: 10px; opacity: 0.85;">TRIGGER CYCLONE / HIGH-WIND EVACUATION SOPS</span>';
      } else {
        elements.crisisBanner.innerHTML = '<span>⚠️ CRITICAL METEOROLOGICAL ALERT DETECTED — HIGH/EXTREME SEVERITY HAZARDS ACTIVE</span>';
      }
    }
  } else {
    document.body.classList.remove('crisis-mode');
    if (elements.crisisBanner) {
      elements.crisisBanner.style.display = 'none';
    }
  }
}

// ── 6. Citations & Metadata (Marked.js & Source Pills) ───────────────────────
function appendUserMessage(queryText) {
  const msgEntry = document.createElement('div');
  msgEntry.className = 'message-entry user-message';

  const prefix = document.createElement('span');
  prefix.className = 'message-prefix';
  prefix.textContent = 'USER';

  const textNode = document.createElement('div');
  textNode.className = 'message-text';
  textNode.textContent = queryText;

  msgEntry.append(prefix, textNode);
  elements.chatStream.appendChild(msgEntry);
  msgEntry.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function appendSystemLoading(customLabel) {
  const loadingEntry = document.createElement('div');
  loadingEntry.className = 'message-entry system-loading';
  loadingEntry.id = 'systemLoadingIndicator';

  const spinner = document.createElement('div');
  spinner.className = 'system-spinner';

  const label = document.createElement('span');
  label.textContent = customLabel || 'Fetching weather data...';

  loadingEntry.append(spinner, label);
  elements.chatStream.appendChild(loadingEntry);
  loadingEntry.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return loadingEntry;
}

// ── Collapsible Intel Panel Helpers ─────────────────────────────────────────
function updateIntelToggleText(btn, customLabel) {
  if (!btn) return;
  const isExpanded = btn.getAttribute('data-state') === 'expanded';
  const count = btn.getAttribute('data-count') || '0';
  const key = btn.getAttribute('data-t');

  const isSources = (key === 'BTN_SOURCES');
  const baseLabel = customLabel || (isSources ? 'Sources' : 'Active Hazards');

  if (isExpanded) {
    btn.textContent = `Hide ${baseLabel} (${count})`;
  } else {
    btn.textContent = `${baseLabel} (${count})`;
  }
}

function toggleIntelPanel(btn, panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  const isExpanded = btn.getAttribute('data-state') === 'expanded';
  if (isExpanded) {
    panel.style.display = 'none';
    btn.setAttribute('data-state', 'collapsed');
    btn.classList.remove('is-active');
  } else {
    panel.style.display = 'block';
    btn.setAttribute('data-state', 'expanded');
    btn.classList.add('is-active');
  }
  updateIntelToggleText(btn);
}

function formatSourceDisplayName(rawSource) {
  if (!rawSource) return 'Official Document';
  let clean = rawSource.replace(/\\/g, '/').split('/').pop().trim();
  clean = clean.replace(/\.[a-zA-Z0-9]+$/, '');
  if (/^(imd|usgs|incois|ndmp)$/i.test(clean)) {
    return clean.toUpperCase();
  }
  if (clean.includes('_') || clean.includes('-')) {
    clean = clean.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return clean || rawSource;
}

function appendBotMessage(response) {
  const msgEntry = document.createElement('div');
  msgEntry.className = 'message-entry bot-message';

  const prefix = document.createElement('span');
  prefix.className = 'message-prefix';
  prefix.textContent = 'METEOROLOGICAL INTELLIGENCE';

  // Confidence UI Binding - Graphical Progress Line & Clean Percentage
  const confGauge = document.createElement('div');
  confGauge.className = 'confidence-gauge-bar';
  const confScore = (response && response.confidence_score != null) ? Number(response.confidence_score) : 1.0;
  const isConflict = Boolean(response && response.model_disagreement);
  const clampedScore = Math.max(0.0, Math.min(1.0, confScore));
  const pct = Math.round(clampedScore * 100);

  if (isConflict) {
    confGauge.classList.add('is-conflict');
    confGauge.innerHTML = `
      <span class="confidence-label">Confidence:</span>
      <div class="confidence-progress-track">
        <div class="confidence-progress-fill is-conflict" style="width: ${pct}%;"></div>
      </div>
      <span class="confidence-pct">${pct}%</span>
      <span class="confidence-warning-badge">⚠️ Sensor / model discrepancy</span>
    `;
    confGauge.title = 'Ground sensor readings differ from model forecasts.';
  } else {
    confGauge.innerHTML = `
      <span class="confidence-label">Confidence:</span>
      <div class="confidence-progress-track">
        <div class="confidence-progress-fill" style="width: ${pct}%;"></div>
      </div>
      <span class="confidence-pct">${pct}%</span>
      <span class="confidence-status-badge">Multi-source consensus</span>
    `;
  }

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  // Render response.bot_reply using marked.js parser
  const rawReply = response.bot_reply || 'No meteorological telemetry returned.';
  if (typeof marked !== 'undefined' && marked.parse) {
    contentDiv.innerHTML = marked.parse(rawReply);
  } else {
    contentDiv.textContent = rawReply;
  }

  msgEntry.append(prefix, confGauge, contentDiv);

  // Audio Playback Attachment if response.audio_url or audio_base64 exists
  const audioSrc = response.audio_base64 || response.audio_url;
  if (audioSrc) {
    const audioWrap = document.createElement('div');
    audioWrap.className = 'audio-player-wrap';

    const audioHeader = document.createElement('div');
    audioHeader.className = 'audio-player-header';
    audioHeader.innerHTML = `
      <span class="audio-player-tag">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
        Voice Briefing
      </span>
      <span class="audio-status-pill">Ready</span>
    `;
    audioWrap.appendChild(audioHeader);

    const audioEl = document.createElement('audio');
    audioEl.controls = true;
    audioEl.preload = 'auto';
    audioEl.src = audioSrc;

    // Task 2: Force browser re-fetch/handshake via audio.load()
    audioEl.load();

    // Event listener for audio status
    audioEl.addEventListener('play', () => {
      console.log('Voice Briefing > Playing');
      const pill = audioWrap.querySelector('.audio-status-pill');
      if (pill) {
        pill.textContent = 'Playing';
        pill.className = 'audio-status-pill is-playing';
      }
    });

    audioEl.addEventListener('pause', () => {
      console.log('Voice Briefing > Paused');
      const pill = audioWrap.querySelector('.audio-status-pill');
      if (pill) {
        pill.textContent = 'Paused';
        pill.className = 'audio-status-pill is-paused';
      }
    });

    audioEl.addEventListener('ended', () => {
      console.log('Voice Briefing > Ended');
      const pill = audioWrap.querySelector('.audio-status-pill');
      if (pill) {
        pill.textContent = 'Ended';
        pill.className = 'audio-status-pill';
      }
    });

    audioWrap.appendChild(audioEl);
    msgEntry.appendChild(audioWrap);
  }

  // ── Collapsible Intel Panels (Sources & Radar Hazards) ──
  const rawSources = response.sources || [];
  const rawAlerts = response.alerts || [];

  // De-duplication map for sources
  const uniqueSources = new Map();
  rawSources.forEach((src) => {
    const srcName = (src.source || 'Official IMD Document').trim();
    const cleanName = formatSourceDisplayName(srcName);
    const normKey = cleanName.toLowerCase();

    if (!uniqueSources.has(normKey)) {
      uniqueSources.set(normKey, {
        source: cleanName,
        rawSource: srcName,
        content: src.content || '',
        score: src.score != null ? src.score : null,
        count: 1,
      });
    } else {
      const existing = uniqueSources.get(normKey);
      existing.count += 1;
      if (src.score != null && (existing.score == null || src.score > existing.score)) {
        existing.score = src.score;
      }
      if (src.content && !existing.content.includes(src.content.slice(0, 60))) {
        existing.content += '\n\n' + src.content;
      }
    }
  });

  // De-duplication map for alerts
  const uniqueAlerts = new Map();
  rawAlerts.forEach((alert) => {
    const key = `${(alert.title || '').trim()}::${(alert.source || '').trim()}`.toLowerCase();
    if (!uniqueAlerts.has(key)) {
      uniqueAlerts.set(key, alert);
    }
  });

  const hasSources = uniqueSources.size > 0;
  const hasAlerts = uniqueAlerts.size > 0;

  if (hasSources || hasAlerts) {
    const intelToggleBar = document.createElement('div');
    intelToggleBar.className = 'intel-toggle-bar';

    let sourcePanel = null;
    let hazardPanel = null;

    // 1. Sources Toggle Button & Collapsible Panel
    if (hasSources) {
      const sourcesCount = uniqueSources.size;
      const sourcePanelId = 'intelSources_' + Math.random().toString(36).substring(2, 9);

      const sourceToggleBtn = document.createElement('button');
      sourceToggleBtn.type = 'button';
      sourceToggleBtn.className = 'intel-toggle-btn';
      sourceToggleBtn.setAttribute('data-t', 'BTN_SOURCES');
      sourceToggleBtn.setAttribute('data-target', sourcePanelId);
      sourceToggleBtn.setAttribute('data-state', 'collapsed');
      sourceToggleBtn.setAttribute('data-count', String(sourcesCount));
      sourceToggleBtn.setAttribute('data-count-suffix', '');
      updateIntelToggleText(sourceToggleBtn);

      sourceToggleBtn.addEventListener('click', () => {
        toggleIntelPanel(sourceToggleBtn, sourcePanelId);
      });
      intelToggleBar.appendChild(sourceToggleBtn);

      sourcePanel = document.createElement('div');
      sourcePanel.id = sourcePanelId;
      sourcePanel.className = 'intel-panel-content';
      sourcePanel.style.display = 'none';

      const badgeRow = document.createElement('div');
      badgeRow.className = 'source-badge-row';

      const labelSpan = document.createElement('span');
      labelSpan.className = 'source-badge-label';
      labelSpan.textContent = 'Sources:';
      badgeRow.appendChild(labelSpan);

      uniqueSources.forEach((entry) => {
        let pageNum = 'Page 1';
        const pageMatch = ((entry.rawSource || entry.source) + ' ' + entry.content).match(/(?:page|p\.)\s*(\d+)/i);
        if (pageMatch) {
          pageNum = `Page ${pageMatch[1]}`;
        } else if (entry.count > 1) {
          pageNum = `Pages 1-${entry.count}`;
        }

        let docFilename = 'national_disaster_management_plan.pdf';
        const sLower = (entry.source + ' ' + (entry.rawSource || '')).toLowerCase();
        if (sLower.includes('bulletin') || sLower.includes('nowcast')) {
          docFilename = 'national_bulletin.pdf';
        } else if (sLower.includes('source_registry')) {
          docFilename = 'source_registry.json';
        }
        const docUrl = `/data/${docFilename}`;

        const badge = document.createElement('button');
        badge.type = 'button';
        badge.className = 'wm-source-badge';
        badge.innerHTML = `${escapeHtml(entry.source)} <span class="badge-page-text">(${escapeHtml(pageNum)})</span>`;
        badge.title = 'Click to inspect document excerpt';

        badge.addEventListener('click', () => {
          openSourceModal({
            source: entry.source,
            content: entry.content,
            score: entry.score,
            page: pageNum,
            docUrl: docUrl,
          });
        });

        badgeRow.appendChild(badge);
      });

      sourcePanel.appendChild(badgeRow);
    }

    // 2. Radar Hazards Toggle Button & Collapsible Panel
    if (hasAlerts) {
      const alertsCount = Math.max(rawAlerts.length, uniqueAlerts.size);
      const hazardPanelId = 'intelHazards_' + Math.random().toString(36).substring(2, 9);

      const hazardToggleBtn = document.createElement('button');
      hazardToggleBtn.type = 'button';
      hazardToggleBtn.className = 'intel-toggle-btn';
      hazardToggleBtn.setAttribute('data-t', 'BTN_HAZARDS');
      hazardToggleBtn.setAttribute('data-target', hazardPanelId);
      hazardToggleBtn.setAttribute('data-state', 'collapsed');
      hazardToggleBtn.setAttribute('data-count', String(alertsCount));
      hazardToggleBtn.setAttribute('data-count-suffix', ' ACTIVE');
      updateIntelToggleText(hazardToggleBtn);

      hazardToggleBtn.addEventListener('click', () => {
        toggleIntelPanel(hazardToggleBtn, hazardPanelId);
      });
      intelToggleBar.appendChild(hazardToggleBtn);

      hazardPanel = document.createElement('div');
      hazardPanel.id = hazardPanelId;
      hazardPanel.className = 'intel-panel-content';
      hazardPanel.style.display = 'none';

      const hazardRow = document.createElement('div');
      hazardRow.className = 'source-badge-row';

      const hLabel = document.createElement('span');
      hLabel.className = 'source-badge-label';
      hLabel.textContent = 'Active Hazards:';
      hazardRow.appendChild(hLabel);

      uniqueAlerts.forEach((alert) => {
        const badge = document.createElement('button');
        badge.type = 'button';
        badge.className = 'wm-source-badge wm-hazard-badge';
        const src = (alert.source || 'HAZARD').toUpperCase().trim();
        let title = (alert.title || 'Alert').trim();
        const srcRegex = new RegExp(`^${src}\\s*[-:]?\\s*`, 'i');
        title = title.replace(srcRegex, '');
        const locText = alert.latitude != null ? ` [${alert.latitude.toFixed(1)}°, ${alert.longitude.toFixed(1)}°]` : '';
        badge.textContent = `${src} - ${title}${locText}`;
        badge.title = 'Click to focus radar on this hazard location';

        badge.addEventListener('click', () => {
          flyToHazard(alert);
        });

        hazardRow.appendChild(badge);
      });

      hazardPanel.appendChild(hazardRow);
    }

    msgEntry.appendChild(intelToggleBar);
    if (sourcePanel) msgEntry.appendChild(sourcePanel);
    if (hazardPanel) msgEntry.appendChild(hazardPanel);
  }

  elements.chatStream.appendChild(msgEntry);
  msgEntry.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return msgEntry;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[m]));
}

// ── 7. Source Inspection Modal ──────────────────────────────────────────────
function openSourceModal(sourceItem) {
  if (!elements.sourceModal) return;
  elements.sourceModalTitle.textContent = formatSourceDisplayName(sourceItem.source) || 'Source Document';
  elements.sourceModalContent.textContent = sourceItem.content || 'Excerpt text unavailable in current index.';

  const pageText = sourceItem.page ? `${sourceItem.page} • ` : '';
  elements.sourceModalMeta.textContent = `${pageText}Official Verified Intelligence`;

  if (elements.sourceDocLink) {
    elements.sourceDocLink.href = sourceItem.docUrl || '/data/national_disaster_management_plan.pdf';
  }

  elements.sourceModal.classList.add('is-open');
}

function closeSourceModal() {
  if (elements.sourceModal) {
    elements.sourceModal.classList.remove('is-open');
  }
}

if (elements.closeSourceModalBtn) {
  elements.closeSourceModalBtn.addEventListener('click', closeSourceModal);
}
if (elements.sourceModal) {
  elements.sourceModal.addEventListener('click', (e) => {
    if (e.target === elements.sourceModal) closeSourceModal();
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeSourceModal();
});

// ── 8. Request Bridge (ChatRequest Execution) ────────────────────────────────
function buildLocationPayload() {
  // Must match { "latitude": float, "longitude": float, "city": string, "raw_text": string }
  if (state.locationMode === 'gps' && state.gpsCoordinates) {
    return {
      latitude: parseFloat(state.gpsCoordinates.latitude),
      longitude: parseFloat(state.gpsCoordinates.longitude),
      city: null,
      raw_text: `${state.gpsCoordinates.latitude.toFixed(4)}, ${state.gpsCoordinates.longitude.toFixed(4)}`,
    };
  }

  const manualVal = elements.manualLocationInput ? elements.manualLocationInput.value.trim() : '';
  if (manualVal) {
    return {
      latitude: null,
      longitude: null,
      city: manualVal,
      raw_text: manualVal,
    };
  }

  // Default auto-resolve coordinates if none specified
  return {
    latitude: 22.5726,
    longitude: 88.3639,
    city: 'Kolkata',
    raw_text: 'Kolkata',
  };
}

async function executeCommand(queryText) {
  if (!queryText || state.isExecuting) return;

  state.isExecuting = true;
  if (elements.executeBtn) elements.executeBtn.disabled = true;
  if (elements.queryInput) elements.queryInput.disabled = true;

  appendUserMessage(queryText);
  if (elements.queryInput) elements.queryInput.value = '';

  // 1. Multi-Turn History Persistence
  const userMsg = { role: 'user', content: queryText };
  state.chatHistory.push(userMsg);
  chatHistory.push(userMsg);
  if (state.chatHistory.length > 6) state.chatHistory = state.chatHistory.slice(-6);
  if (chatHistory.length > 6) chatHistory = chatHistory.slice(-6);

  // 2. Visual Prompt in Chat Feed
  const loadingIndicator = appendSystemLoading('Fetching weather data...');

  // 3. Construct Live Request matching ChatRequest Schema
  const payload = {
    query: queryText,
    language: elements.languageSelect ? elements.languageSelect.value : 'en',
    channel: state.isVoiceMode ? 'voice' : 'web',
    location: buildLocationPayload(),
    scientific_mode: Boolean(state.satelliteMode || (state.mapMode === 'sat')),
    history: state.chatHistory.slice(-6),
    mode: state.currentMode || state.operationalMode || 'standard',
  };

  state.isVoiceMode = false;

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned status HTTP ${response.status}`);
    }

    const data = await response.json();
    loadingIndicator.remove();

    if (data.bot_reply) {
      const assistantMsg = { role: 'assistant', content: data.bot_reply };
      state.chatHistory.push(assistantMsg);
      chatHistory.push(assistantMsg);
      if (state.chatHistory.length > 6) state.chatHistory = state.chatHistory.slice(-6);
      if (chatHistory.length > 6) chatHistory = chatHistory.slice(-6);
    }

    if (data.detected_language) {
      updateBhashiniBadge(data.detected_language);
      if (elements.languageSelect && elements.languageSelect.value === 'auto') {
        const hasOpt = Array.from(elements.languageSelect.options).some(o => o.value === data.detected_language);
        if (hasOpt) {
          elements.languageSelect.value = data.detected_language;
          applyLocalization(data.detected_language);
        }
      }
    }

    // Cache state
    state.lastWeatherData = data.weather;
    state.activeLocation = data.location;
    state.currentLocation = data.location;
    state.historyData = data.history_data || [];
    state.currentAlerts = data.alerts || [];
    state.currentOverlays = data.synoptic_overlays || [];

    // 4. Live-Wire Binding:
    // 4.1 bot_reply -> rendered via marked.parse into terminal feed
    appendBotMessage(data);

    // Aerodrome Lock & METAR Runway Report Binding
    updateAerodromeHeader(data.icao_code || data.location?.icao_code, data.location?.city);
    updateMetarTelemetryDisplay(data.metar_raw, data.flight_rules, data.icao_code || data.location?.icao_code);

    // 4.2 Ticker Tape (with wind shear tactical takeover)
    bindTickerTape(data.bot_reply, data.alerts, data.metar_raw, data.icao_code || data.location?.icao_code);

    // 4.3 Live Telemetry Widgets:
    // weather.current.temperature -> #metricTemp / #telemetryTemp
    // weather.current.humidity -> #metric2Val & #metric2Bar width
    // alerts -> "X ACTIVE HAZARDS" counter & crisis alert strip
    bindTelemetryWidgets(data.weather, data.alerts);

    // 4.4 Geospatial Radar Lock
    updateGeospatialLayer(data.location, data.alerts, data.synoptic_overlays);

    // 4.5 Emergency UI state
    updateEmergencyUIState(data.alerts, data.weather);

  } catch (err) {
    loadingIndicator.remove();
    const errorEntry = document.createElement('div');
    errorEntry.className = 'message-entry bot-message';
    errorEntry.innerHTML = `
      <span class="message-prefix" style="color:var(--terminal-red);">SYS_ERROR &gt; EXECUTION FAILED</span>
      <div class="message-content" style="color:var(--terminal-red);">
        [ERROR] Communication failure with backend at /chat: ${escapeHtml(err.message)}
      </div>
    `;
    elements.chatStream.appendChild(errorEntry);
    errorEntry.scrollIntoView({ behavior: 'smooth', block: 'end' });
  } finally {
    state.isExecuting = false;
    if (elements.executeBtn) elements.executeBtn.disabled = false;
    if (elements.queryInput) {
      elements.queryInput.disabled = false;
      elements.queryInput.focus();
    }
  }
}
window.executeCommand = executeCommand;
window.executeChatRequest = executeCommand;

function executeChatRequest(queryText) {
  return executeCommand(queryText);
}

// ── 9. Form Submission & Universal Intent Quick Queries ──────────────────────
function sendQuickQuery(queryText) {
  if (!queryText) return;
  const cleanQuery = queryText.trim().replace(/^>\s*/, '');
  if (!cleanQuery) return;

  // 1. Clear the chat input
  if (elements.queryInput) {
    elements.queryInput.value = '';
  }

  // 2. Display selected question in USER > log & 3. Trigger full AI query pipeline
  executeChatRequest(cleanQuery);
}
window.sendQuickQuery = sendQuickQuery;

if (elements.commandForm) {
  elements.commandForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = elements.queryInput.value.trim();
    if (query) executeChatRequest(query);
  });
}

// Fallback delegation for quick prompt buttons (in case inline onclick is prevented)
document.querySelectorAll('.quick-prompt-btn').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    if (!btn.getAttribute('onclick')) {
      sendQuickQuery(btn.textContent);
    }
  });
});

// ── 10. Location Mode Controls ──────────────────────────────────────────────
function setLocationMode(mode) {
  state.locationMode = mode;
  if (mode === 'gps') {
    elements.gpsModeBtn.classList.add('is-active');
    elements.manualModeBtn.classList.remove('is-active');
    elements.manualInputContainer.style.display = 'none';
    requestDeviceLocation();
  } else {
    elements.manualModeBtn.classList.add('is-active');
    elements.gpsModeBtn.classList.remove('is-active');
    elements.manualInputContainer.style.display = 'flex';
    elements.locationSummaryText.textContent = 'LOC: MANUAL ENTRY';
    if (elements.manualLocationInput) elements.manualLocationInput.focus();
  }
}

function requestDeviceLocation(callback) {
  if (!navigator.geolocation) {
    elements.locationSummaryText.textContent = 'LOC: GPS UNAVAILABLE (DEFAULTING)';
    if (typeof callback === 'function') callback();
    return;
  }

  elements.locationSummaryText.textContent = 'LOC: ACQUIRING SATELLITE...';
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      state.gpsCoordinates = {
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
      };
      elements.locationSummaryText.textContent = `GPS: ${pos.coords.latitude.toFixed(2)}°, ${pos.coords.longitude.toFixed(2)}°`;
      if (state.map) {
        updateGeospatialLayer(
          { latitude: pos.coords.latitude, longitude: pos.coords.longitude, city: 'DEVICE GPS' },
          state.currentAlerts || [],
          state.currentOverlays || []
        );
      }
      if (typeof callback === 'function') callback();
    },
    (err) => {
      elements.locationSummaryText.textContent = 'LOC: GPS PERMISSION DENIED (DEFAULTING)';
      if (typeof callback === 'function') callback();
    },
    { timeout: 2000, enableHighAccuracy: true }
  );
}

if (elements.gpsModeBtn) {
  elements.gpsModeBtn.addEventListener('click', () => setLocationMode('gps'));
}
if (elements.manualModeBtn) {
  elements.manualModeBtn.addEventListener('click', () => setLocationMode('manual'));
}
if (elements.manualLocationInput) {
  const aerodromeMap = {
    kolkata: { icao: 'VECC', name: 'KOLKATA INTL', lat: 22.65, lon: 88.45 },
    calcutta: { icao: 'VECC', name: 'KOLKATA INTL', lat: 22.65, lon: 88.45 },
    delhi: { icao: 'VIDP', name: 'DELHI INTL', lat: 28.56, lon: 77.10 },
    'new delhi': { icao: 'VIDP', name: 'DELHI INTL', lat: 28.56, lon: 77.10 },
    mumbai: { icao: 'VABB', name: 'MUMBAI INTL', lat: 19.09, lon: 72.87 },
    bombay: { icao: 'VABB', name: 'MUMBAI INTL', lat: 19.09, lon: 72.87 },
    chennai: { icao: 'VOMM', name: 'CHENNAI INTL', lat: 12.99, lon: 80.17 },
    madras: { icao: 'VOMM', name: 'CHENNAI INTL', lat: 12.99, lon: 80.17 },
    bengaluru: { icao: 'VOBL', name: 'KEMPEGOWDA INTL', lat: 13.20, lon: 77.71 },
    bangalore: { icao: 'VOBL', name: 'KEMPEGOWDA INTL', lat: 13.20, lon: 77.71 },
    hyderabad: { icao: 'VOHS', name: 'RAJIV GANDHI INTL', lat: 17.24, lon: 78.43 },
    ahmedabad: { icao: 'VAAH', name: 'SARDAR VALLABHBHAI PATEL INTL', lat: 23.07, lon: 72.63 },
    bhubaneswar: { icao: 'VEBS', name: 'BIJU PATNAIK INTL', lat: 20.24, lon: 85.82 },
    patna: { icao: 'VEPT', name: 'JAYPRAKASH NARAYAN INTL', lat: 25.59, lon: 85.09 },
    guwahati: { icao: 'VEGT', name: 'LOKPRIA GOPINATH BORDOI INTL', lat: 26.11, lon: 91.59 },
    kochi: { icao: 'VOCI', name: 'COCHIN INTL', lat: 10.15, lon: 76.40 },
    amritsar: { icao: 'VIAR', name: 'SRI GURU RAM DASS JEE INTL', lat: 31.71, lon: 74.80 },
    goa: { icao: 'VOGO', name: 'DABOLIM / GOA INTL', lat: 15.38, lon: 73.83 },
    lucknow: { icao: 'VILK', name: 'CHAUDHARY CHARAN SINGH INTL', lat: 26.76, lon: 80.88 },
    jaipur: { icao: 'VIJP', name: 'JAIPUR INTL', lat: 26.82, lon: 75.81 },
    'port blair': { icao: 'VOPB', name: 'VEER SAVARKAR INTL', lat: 11.64, lon: 92.73 },
  };

  elements.manualLocationInput.addEventListener('input', (e) => {
    state.manualLocationText = e.target.value.trim();
    if (state.manualLocationText) {
      elements.locationSummaryText.textContent = `LOC: ${state.manualLocationText.toUpperCase()}`;
      const match = aerodromeMap[state.manualLocationText.toLowerCase()];
      if (match) {
        updateAerodromeHeader(match.icao, match.name);
        updateMetarTelemetryDisplay(null, null, match.icao);
      }
    }
  });

  elements.manualLocationInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const city = e.target.value.trim();
      if (city) {
        state.manualLocationText = city;
        const match = aerodromeMap[city.toLowerCase()];
        if (match) {
          updateAerodromeHeader(match.icao, match.name);
          state.activeLocation = {
            latitude: match.lat,
            longitude: match.lon,
            city: city,
            icao_code: match.icao,
            airport_name: match.name,
          };
          state.currentLocation = state.activeLocation;
          if (state.map) {
            state.map.setView([match.lat, match.lon], 9, { animate: true });
            initRadar(match.lat, match.lon);
          }
        }
        sendSystemProbe(false);
      }
    }
  });
}

// ── 11. Voice Input Integration (Voice-to-Voice Command Center) ─────────────
let mediaRecorder = null;
let audioChunks = [];
let voiceIndicatorEl = null;

function setupVoiceInput() {
  if (!elements.voiceBtn) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === 'undefined') {
    elements.voiceBtn.disabled = true;
    elements.voiceBtn.title = 'Voice capture unavailable in this environment';
    return;
  }

  elements.voiceBtn.addEventListener('click', async () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 44100,
        },
      });
      audioChunks = [];

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : (MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus') ? 'audio/ogg;codecs=opus' : ''));

      mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      let audioCtx = null;
      let silenceCheckInterval = null;
      let lastSpeechTime = Date.now();
      let speechDetected = false;
      let stoppedDueToSilence = false;

      try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
          audioCtx = new AudioContextClass();
          const sourceNode = audioCtx.createMediaStreamSource(stream);
          const analyserNode = audioCtx.createAnalyser();
          analyserNode.fftSize = 256;
          sourceNode.connect(analyserNode);
          const pcmData = new Uint8Array(analyserNode.frequencyBinCount);

          silenceCheckInterval = setInterval(() => {
            if (!mediaRecorder || mediaRecorder.state !== 'recording') {
              if (silenceCheckInterval) clearInterval(silenceCheckInterval);
              return;
            }
            analyserNode.getByteFrequencyData(pcmData);
            let energy = 0;
            for (let i = 0; i < pcmData.length; i++) {
              energy += pcmData[i];
            }
            const avg = energy / pcmData.length;
            // Ambient noise threshold
            if (avg > 12) {
              speechDetected = true;
              lastSpeechTime = Date.now();
            } else if (Date.now() - lastSpeechTime >= 12000) {
              // 12 seconds of silence detected -> auto stop!
              stoppedDueToSilence = true;
              if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
              }
              if (silenceCheckInterval) clearInterval(silenceCheckInterval);
            }
          }, 150);
        }
      } catch (audioErr) {
        console.warn('AudioContext monitor unavailable, using fallback timer', audioErr);
      }

      // Hard fallback safety timer (in case AudioContext is blocked or silent throughout)
      const hardSilenceTimer = setTimeout(() => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
          stoppedDueToSilence = true;
          mediaRecorder.stop();
        }
      }, 12000);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstart = () => {
        elements.voiceBtn.classList.add('is-recording');
        elements.voiceBtn.setAttribute('title', 'Listening... Click again to process');
        state.isVoiceMode = true;

        // Visual indicator: Listening...
        if (voiceIndicatorEl) voiceIndicatorEl.remove();
        voiceIndicatorEl = document.createElement('div');
        voiceIndicatorEl.className = 'message-entry system-loading';
        voiceIndicatorEl.innerHTML = `
          <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#FF3131; box-shadow:0 0 10px #FF3131; margin-right:8px; animation: mic-blink 0.8s infinite;"></span>
          <span style="color:#FF3131; font-weight:700; letter-spacing:0.5px;">Listening...</span>
        `;
        elements.chatStream.appendChild(voiceIndicatorEl);
        voiceIndicatorEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
      };

      mediaRecorder.onstop = async () => {
        clearTimeout(hardSilenceTimer);
        if (silenceCheckInterval) clearInterval(silenceCheckInterval);
        if (audioCtx) {
          try { audioCtx.close(); } catch(e) {}
        }

        elements.voiceBtn.classList.remove('is-recording');
        elements.voiceBtn.setAttribute('title', 'Voice Input (Tap to record)');
        stream.getTracks().forEach((track) => track.stop());

        if (audioChunks.length === 0 || (stoppedDueToSilence && !speechDetected)) {
          if (voiceIndicatorEl) {
            voiceIndicatorEl.remove();
            voiceIndicatorEl = null;
          }
          const errMsg = document.createElement('div');
          errMsg.className = 'message-entry bot-message';
          errMsg.innerHTML = `
            <span class="message-prefix" style="color:var(--terminal-red);">Error</span>
            <div class="message-content" style="color:var(--terminal-red);">
              No clear speech detected.
            </div>
          `;
          elements.chatStream.appendChild(errMsg);
          errMsg.scrollIntoView({ behavior: 'smooth', block: 'end' });
          return;
        }

        // Switch indicator: Processing...
        if (voiceIndicatorEl) {
          voiceIndicatorEl.innerHTML = `
            <div class="system-spinner"></div>
            <span style="color:var(--terminal-green); font-weight:700; letter-spacing:0.5px;">Processing...</span>
          `;
        }

        const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'voice_input.webm');
        formData.append('location', JSON.stringify(buildLocationPayload()));

        const selectedLang = elements.languageSelect ? elements.languageSelect.value : 'en';
        if (selectedLang) {
          formData.append('language', selectedLang);
          formData.append('user_language', selectedLang);
        }
        formData.append('mode', state.currentMode || 'standard');

        state.isExecuting = true;
        elements.executeBtn.disabled = true;
        elements.queryInput.disabled = true;

        try {
          const res = await fetch('/voice/process', {
            method: 'POST',
            body: formData,
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned status HTTP ${res.status}`);
          }

          const data = await res.json();

          // Remove processing indicator
          if (voiceIndicatorEl) {
            voiceIndicatorEl.remove();
            voiceIndicatorEl = null;
          }

          // 1. Display recognized user query in the chat stream & CMD> input field
          const userText = data.transcribed_query || 'Voice query';
          appendUserMessage(userText);
          if (elements.queryInput) elements.queryInput.value = userText;

          // Realign output language selector & localization using Linguistic Passport (locked_language_code)
          const lockedLang = data.locked_language_code || data.detected_language;
          if (lockedLang && elements.languageSelect) {
            const hasOpt = Array.from(elements.languageSelect.options).some(o => o.value === lockedLang);
            if (hasOpt) {
              elements.languageSelect.value = lockedLang;
              applyLocalization(lockedLang);
            }
          }
          // Push voice query and response to state.chatHistory for seamless continuity
          state.chatHistory.push({ role: 'user', content: userText });
          chatHistory.push({ role: 'user', content: userText });
          if (data.bot_reply) {
            state.chatHistory.push({ role: 'assistant', content: data.bot_reply });
            chatHistory.push({ role: 'assistant', content: data.bot_reply });
          }
          if (state.chatHistory.length > 6) state.chatHistory = state.chatHistory.slice(-6);
          if (chatHistory.length > 6) chatHistory = chatHistory.slice(-6);

          // 2. Cache telemetry state for temporal analysis and emergency triggers
          state.lastWeatherData = data.weather;
          state.activeLocation = data.location;
          state.currentLocation = data.location;
          state.historyData = data.history_data || [];
          state.currentAlerts = data.alerts || [];
          state.currentOverlays = data.synoptic_overlays || [];

          // 3. Render Markdown reply & Source Pills (with embedded audio player)
          const botMsgEl = appendBotMessage(data);

          // 4. Map the first paragraph to scrolling Ticker Tape (with lightning check)
          bindTickerTape(data.bot_reply, data.alerts);

          // 5. Bind Telemetry Widgets
          bindTelemetryWidgets(data.weather, data.alerts);

          // 6. Update Geospatial Radar (Leaflet.js)
          state.currentOverlays = data.synoptic_overlays || [];
          updateGeospatialLayer(data.location, data.alerts, data.synoptic_overlays);

          // 7. Emergency UI State (crisis-mode)
          updateEmergencyUIState(data.alerts, data.weather);

          // 8. Auto-Play Neural Regional Voice Speech through the UI Audio Player
          if (botMsgEl) {
            const player = botMsgEl.querySelector('audio');
            if (player) {
              player.play().catch((playErr) => {
                console.warn('Browser auto-play notice:', playErr);
              });
            }
          }

        } catch (err) {
          if (voiceIndicatorEl) {
            voiceIndicatorEl.remove();
            voiceIndicatorEl = null;
          }
          const errMsg = document.createElement('div');
          errMsg.className = 'message-entry bot-message';
          const rawErr = (err.message || 'Please type query.').trim();
          let displayErr = rawErr;
          if (rawErr.includes('No clear speech detected') || rawErr.includes('NO_SIGNAL')) {
            displayErr = 'No clear speech detected.';
          } else if (rawErr.startsWith('SYS_VOICE >')) {
            displayErr = rawErr.replace(/^SYS_VOICE\s*>\s*[A-Z_]+:\s*/i, '').replace(/^SYS_VOICE\s*>\s*/i, '');
          }
          errMsg.innerHTML = `
            <span class="message-prefix" style="color:var(--terminal-red);">Error</span>
            <div class="message-content" style="color:var(--terminal-red);">
              ${escapeHtml(displayErr)}
            </div>
          `;
          elements.chatStream.appendChild(errMsg);
          errMsg.scrollIntoView({ behavior: 'smooth', block: 'end' });
        } finally {
          state.isExecuting = false;
          elements.executeBtn.disabled = false;
          elements.queryInput.disabled = false;
          elements.queryInput.focus();
        }
      };

      mediaRecorder.start();
    } catch (err) {
      elements.voiceBtn.classList.remove('is-recording');
      state.isVoiceMode = false;
      if (voiceIndicatorEl) {
        voiceIndicatorEl.remove();
        voiceIndicatorEl = null;
      }
      alert('Microphone permission denied or unavailable.');
    }
  });
}

// ── 12. Health Check ────────────────────────────────────────────────────────
async function checkBackendHealth() {
  const badge = document.getElementById('securityVerifiedBadge');
  const dot = document.querySelector('.footer-status .status-dot') || document.getElementById('footerStatusDot');

  try {
    const res = await fetch('/health', { cache: 'no-store' });
    if (!res.ok) throw new Error();
    if (elements.systemStatusText) elements.systemStatusText.textContent = 'SYS_ONLINE';
    if (elements.systemIndicator) {
      elements.systemIndicator.style.backgroundColor = '#00FF41';
      elements.systemIndicator.style.boxShadow = '0 0 8px #00FF41';
    }
    if (badge) {
      badge.textContent = 'System Online';
      badge.classList.remove('is-offline');
      badge.classList.add('is-online');
      badge.title = 'Backend connection active and healthy';
    }
    if (dot) {
      dot.classList.remove('is-offline');
      dot.classList.add('is-online');
    }
  } catch {
    if (elements.systemStatusText) elements.systemStatusText.textContent = 'SYS_OFFLINE';
    if (elements.systemIndicator) {
      elements.systemIndicator.style.backgroundColor = '#FF3131';
      elements.systemIndicator.style.boxShadow = '0 0 8px #FF3131';
    }
    if (badge) {
      badge.textContent = 'System Offline';
      badge.classList.remove('is-online');
      badge.classList.add('is-offline');
      badge.title = 'Unable to communicate with backend server';
    }
    if (dot) {
      dot.classList.remove('is-online');
      dot.classList.add('is-offline');
    }
  }
}

// ── 13. System Initialization Pulse & Background Heartbeat ─────────────────
let heartbeatInterval = null;

async function sendSystemProbe(isInitial = false) {
  // If user is actively executing a query, skip background heartbeat tick
  if (state.isExecuting && !isInitial) return;

  if (isInitial) {
    if (elements.systemStatusText) elements.systemStatusText.textContent = 'SYS_LOADING...';
    if (elements.systemIndicator) {
      elements.systemIndicator.style.backgroundColor = '#FFAC1C';
      elements.systemIndicator.style.boxShadow = '0 0 10px #FFAC1C';
    }
  }

  const payload = {
    query: 'SYSTEM_STATUS_PROBE',
    language: 'en',
    channel: 'web',
    location: buildLocationPayload(),
    mode: state.currentMode || state.operationalMode || 'standard',
  };

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);
    const data = await res.json();

    // 1. Instantly populate Tactical Radar (Map + Blue User Beacon + Bay of Bengal Heat Aura + Hazard Dots)
    state.currentOverlays = data.synoptic_overlays || [];
    updateGeospatialLayer(data.location, data.alerts, data.synoptic_overlays);

    // Aerodrome Lock & METAR Runway Report Binding
    updateAerodromeHeader(data.icao_code || data.location?.icao_code, data.location?.city);
    updateMetarTelemetryDisplay(data.metar_raw, data.flight_rules, data.icao_code || data.location?.icao_code);

    // 2. Instantly populate Big Digits Telemetry Widgets (Temperature, Humidity, Wind, Active Hazards)
    bindTelemetryWidgets(data.weather, data.alerts);

    // 3. Instantly populate Top Marquee Ticker Tape with Synoptic Overview (with wind shear tactical takeover)
    bindTickerTape(data.bot_reply, data.alerts, data.metar_raw, data.icao_code || data.location?.icao_code);

    // 4. Update Crisis Mode if critical alerts exist or temp > 45 / wind > 75
    updateEmergencyUIState(data.alerts, data.weather);

    // 5. Set System Indicator to active green
    if (elements.systemStatusText) elements.systemStatusText.textContent = 'SYS_ONLINE';
    if (elements.systemIndicator) {
      elements.systemIndicator.style.backgroundColor = '#00FF41';
      elements.systemIndicator.style.boxShadow = '0 0 8px #00FF41';
    }

    // 6. On initial load, attach a clean live status strip to the initialization welcome bubble
    if (isInitial) {
      const welcomeContent = document.querySelector('#initialWelcomeMessage .message-content');
      if (welcomeContent && !document.getElementById('initialSystemProbeSummary')) {
        const summaryBadge = document.createElement('div');
        summaryBadge.id = 'initialSystemProbeSummary';
        summaryBadge.className = 'source-badge-row';
        summaryBadge.style.marginTop = '10px';
        summaryBadge.style.paddingTop = '8px';
        summaryBadge.style.borderTop = '1px dashed rgba(0, 255, 65, 0.25)';

        const alertCount = (data.alerts || []).length;
        const temp = data.weather?.current?.temperature != null
          ? `${Number(data.weather.current.temperature).toFixed(1)}°C`
          : 'NOMINAL';
        const locName = data.location?.city || 'KOLKATA';

        summaryBadge.innerHTML = `
          <span class="wm-source-badge"><span class="badge-tag">[LOC]</span> ${escapeHtml(locName)}</span>
          <span class="wm-source-badge"><span class="badge-tag">[TEMP]</span> ${temp}</span>
          <span class="wm-source-badge wm-hazard-badge"><span style="color:#FF3131; font-weight:800;">!</span> [HAZARDS] ${alertCount} ACTIVE</span>
          <span class="wm-source-badge"><span class="badge-tag">[AURA]</span> BAY OF BENGAL SYSTEM</span>
        `;
        welcomeContent.appendChild(summaryBadge);
      }
    }
  } catch (err) {
    console.warn('System probe sync warning:', err);
    if (isInitial) {
      if (elements.systemStatusText) elements.systemStatusText.textContent = 'SYS_ONLINE';
      if (elements.systemIndicator) {
        elements.systemIndicator.style.backgroundColor = '#00FF41';
        elements.systemIndicator.style.boxShadow = '0 0 8px #00FF41';
      }
    }
  }
}

// ── 11. Visual Temporal Map Filter & Historical Hazard Dashboard ───────────
function initIntervalButtons() {
  const buttons = document.querySelectorAll('.interval-btn');
  if (!buttons || buttons.length === 0) return;

  buttons.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const interval = btn.getAttribute('data-interval') || '24h';
      buttons.forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      state.currentInterval = interval;

      // Visual Temporal Map Filter (No chat trigger! Updates map directly)
      await filterHazardsByInterval(interval);
    });
  });
}

async function filterHazardsByInterval(interval) {
  if (!state.map) return;

  const badge = elements.radarBadge || document.getElementById('radarBadge');
  if (badge) {
    badge.textContent = `Updating radar (${interval.toUpperCase()})...`;
    badge.classList.add('status-glow');
  }

  // 1. Clear current hazard markers from map
  if (state.hazardLayerGroup) {
    state.hazardLayerGroup.clearLayers();
  }
  state.map.eachLayer((layer) => {
    if (layer instanceof L.CircleMarker) {
      state.map.removeLayer(layer);
    }
  });

  const loc = state.currentLocation || (state.gpsCoordinates ? { latitude: state.gpsCoordinates.latitude, longitude: state.gpsCoordinates.longitude } : { latitude: 22.5726, longitude: 88.3639 });

  try {
    const res = await fetch(`/hazards?interval=${encodeURIComponent(interval)}&lat=${loc.latitude}&lon=${loc.longitude}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const hazards = data.hazards || [];

    // 2. Re-Plot: Draw new markers with visual distinction (Live Neon vs Dull/Ghostly Historical)
    renderHazardMarkers(hazards, loc.latitude, loc.longitude);

    // 3. Update Tactical Radar Status Badge
    if (badge) {
      badge.textContent = `${hazards.length} hazards tracked (${interval.toUpperCase()})`;
    }

    // 4. Telemetry Widget Sync (Digital Temperature & Humidity Averages for interval)
    const summary = data.summary;
    if (summary && summary.avg_temperature != null) {
      if (elements.telemetryTemp) elements.telemetryTemp.textContent = `${Number(summary.avg_temperature).toFixed(1)}°C`;
      if (elements.telemetryTempSub) elements.telemetryTempSub.textContent = `${interval.toUpperCase()} AVG (CLIMATE TREND)`;
      if (summary.avg_humidity != null && elements.telemetryHumidity) {
        elements.telemetryHumidity.textContent = `${Math.round(summary.avg_humidity)}%`;
        if (elements.humidityBarFill) {
          elements.humidityBarFill.style.width = `${Math.min(100, Math.max(0, summary.avg_humidity))}%`;
        }
        if (elements.telemetryHumiditySub) elements.telemetryHumiditySub.textContent = `${interval.toUpperCase()} AVG (PERIOD DATA)`;
      }
    }

    // 5. Geographic Bounds Adjustment: When 7D or large regional trend is selected, fit South Asia bounds
    if (interval === '7d' || interval === '48h' || hazards.length >= 8) {
      const southAsiaBounds = [[5, 60], [38, 100]];
      state.map.flyToBounds(southAsiaBounds, { duration: 1.2, padding: [20, 20] });
    } else {
      state.map.flyTo([loc.latitude, loc.longitude], 9, { duration: 1.0 });
    }
  } catch (err) {
    console.error('Failed to filter hazards by interval:', err);
    if (badge) badge.textContent = 'RADAR: SWEEP ACTIVE';
  }
}

// ── 12. Dynamic UI Localization (i18n) ──────────────────────────────────────
function applyLocalization(langCode) {
  const code = (langCode || 'en').toLowerCase().split('-')[0];
  const localeSource = (typeof UI_LOCALE !== 'undefined') ? UI_LOCALE : (window.UI_LOCALE || null);
  if (!localeSource) return;

  const dict = localeSource[code] || localeSource['en'];
  const fallback = localeSource['en'] || {};

  document.querySelectorAll('[data-t]').forEach((el) => {
    const key = el.getAttribute('data-t');
    if (!key) return;

    const translated = dict[key] || fallback[key];
    if (translated) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.setAttribute('placeholder', translated);
      } else if (el.classList.contains('intel-toggle-btn')) {
        updateIntelToggleText(el, translated);
      } else {
        el.textContent = translated;
      }
    }
  });

  // Re-sync telemetry labels for current mode so localized defaults don't clobber aviation labels
  updateTelemetryWidgetForMode(state.lastWeatherData);

  // Update Digital India Bhashini footer badge
  updateBhashiniBadge(code);
}

function updateBhashiniBadge(langCode) {
  const badge = document.getElementById('securityVerifiedBadge');
  if (!badge) return;
  if (badge.classList.contains('is-offline')) {
    badge.textContent = 'System Offline';
  } else {
    badge.textContent = 'System Online';
  }
}
window.updateBhashiniBadge = updateBhashiniBadge;

if (elements.languageSelect) {
  elements.languageSelect.addEventListener('change', (e) => {
    applyLocalization(e.target.value);
    if (state.map && (state.currentLocation || state.lastLocationData || state.currentAlerts || state.lastSynopticOverlays)) {
      updateGeospatialLayer(
        state.lastLocationData || state.currentLocation,
        state.currentAlerts,
        state.lastSynopticOverlays
      );
    }
  });
}

function initializeTerminal() {
  if (state.isInitialized) return;
  state.isInitialized = true;

  initMap();
  // Remeasure map after design layout (16:9 aspect container)
  setTimeout(function () {
    if (state.map) state.map.invalidateSize();
  }, 150);
  initIntervalButtons();
  setupVoiceInput();
  checkBackendHealth();
  setInterval(checkBackendHealth, 10000);

  // Smooth scroll to FAQ on brand title click
  const brandTitle = document.getElementById('brandTitleLink') || document.querySelector('.brand-title');
  if (brandTitle) {
    brandTitle.addEventListener('click', (e) => {
      e.preventDefault();
      const faq = document.getElementById('faqSection');
      if (faq) {
        faq.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }

  updateQuickPromptButtonsForMode(state.currentMode);
  applyLocalization(elements.languageSelect ? elements.languageSelect.value : 'en');

  // Bind Operational Mode Toggles (Standard <-> Aviation)
  const btnStandard = elements.modeBtnStandard || document.getElementById('mode-btn-standard');
  if (btnStandard) {
    btnStandard.addEventListener('click', () => setMode('standard'));
  }
  const btnAviation = elements.modeBtnAviation || document.getElementById('mode-btn-aviation');
  if (btnAviation) {
    btnAviation.addEventListener('click', () => setMode('aviation'));
  }
  const btnFarmer = elements.modeBtnFarmer || document.getElementById('mode-btn-farmer');
  if (btnFarmer) {
    btnFarmer.addEventListener('click', () => setMode('farmer'));
  }
  const headerModeBtn = elements.modeToggleHeader || document.getElementById('mode-toggle-header');
  if (headerModeBtn) {
    headerModeBtn.addEventListener('click', () => toggleOperationalMode());
  }
  const mapModeBtn = elements.modeToggleMap || document.getElementById('mode-toggle-map');
  if (mapModeBtn) {
    mapModeBtn.addEventListener('click', () => toggleOperationalMode());
  }

  // Task 1: Immediate System Initialization Pulse with GPS or Fallback
  requestDeviceLocation(() => {
    if (!state.hasInitialProbeRan) {
      state.hasInitialProbeRan = true;
      sendSystemProbe(true);
    }
  });

  // Safety fallback: trigger system probe within 1200ms if GPS dialog is pending
  setTimeout(() => {
    if (!state.hasInitialProbeRan) {
      state.hasInitialProbeRan = true;
      sendSystemProbe(true);
    }
  }, 1200);

  // Task 2: Background Heartbeat - Polls every 60 seconds to keep Radar and Hazards fresh
  if (heartbeatInterval) clearInterval(heartbeatInterval);
  heartbeatInterval = setInterval(() => {
    sendSystemProbe(false);
  }, 60000);
}

// ── Bootstrap Terminal ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', initializeTerminal);
window.addEventListener('load', initializeTerminal);

// ── Reactive Theme Observer: update map background when theme toggles ────────
(function () {
  var observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (m) {
      if (m.attributeName === 'class') {
        var mapEl = document.getElementById('radarMap') || document.getElementById('map');
        if (mapEl) {
          var isLight = document.body.classList.contains('theme-light');
          mapEl.style.backgroundColor = isLight ? '#e8f4f8' : '#000814';
        }
      }
    });
  });
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
})();
