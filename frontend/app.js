/**
 * WEATHERGPT-TERMINAL 
 * Full-Stack Integration with FastAPI Backend & Pydantic Schemas
 */

// ── State Management ────────────────────────────────────────────────────────
const state = {
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
  hasInitialProbeRan: false,
  isInitialized: false,
  currentInterval: '24h',
  historyData: [],
  lastWeatherData: null,
  currentLocation: null,
};

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
  telemetryTemp: document.getElementById('telemetryTemp'),
  telemetryTempSub: document.getElementById('telemetryTempSub'),
  telemetryHumidity: document.getElementById('telemetryHumidity'),
  telemetryHumiditySub: document.getElementById('telemetryHumiditySub'),
  humidityBarFill: document.getElementById('humidityBarFill'),
  telemetryWind: document.getElementById('telemetryWind'),
  telemetryWindSub: document.getElementById('telemetryWindSub'),
  telemetryAlertsCount: document.getElementById('telemetryAlertsCount'),
  telemetryBaroSub: document.getElementById('telemetryBaroSub'),
  sourceModal: document.getElementById('sourceModal'),
  sourceModalTitle: document.getElementById('sourceModalTitle'),
  sourceModalContent: document.getElementById('sourceModalContent'),
  sourceModalMeta: document.getElementById('sourceModalMeta'),
  sourceDocLink: document.getElementById('sourceDocLink'),
  closeSourceModalBtn: document.getElementById('closeSourceModalBtn'),
  intervalBtnRow: document.getElementById('intervalBtnRow'),
  radarBadge: document.getElementById('radarBadge'),
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

// ── 2. Geospatial Layer (Leaflet.js) ────────────────────────────────────────
function initMap() {
  const mapElement = document.getElementById('radarMap');
  if (!mapElement || typeof L === 'undefined') return;

  // Initialize map centered on South Asia / India: Bounds [5, 60] to [38, 100]
  state.map = L.map('radarMap', {
    attributionControl: false,
    zoomControl: true,
  });

  const southAsiaBounds = [[5, 60], [38, 100]];
  state.map.fitBounds(southAsiaBounds);

  // Standard OpenStreetMap tiles (darkened via CSS filter in style.css)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
  }).addTo(state.map);

  // Dedicated layer groups for Synoptic Heatmaps and Multi-Hazard markers
  state.synopticLayerGroup = L.layerGroup().addTo(state.map);
  state.hazardLayerGroup = L.layerGroup().addTo(state.map);

  // Initialize Geospatially Anchored Tactical Radar (pinned to default Kolkata coords)
  initRadar(22.5726, 88.3639);
}

/**
 * Creates the Leaflet DivIcon for the Geospatially Anchored Sonar Radar.
 * Pinned directly to coordinates, featuring a 360-degree rotating green beam,
 * continuous 3-ring sonar ripples, and a pulsing transmitter center point.
 */
function createRadarIcon() {
  return L.divIcon({
    className: 'sonar-radar-leaflet-icon',
    html: `
      <div class="sonar-radar-container">
        <div class="radar-sweep"></div>
        <div class="sonar-wave wave-1"></div>
        <div class="sonar-wave wave-2"></div>
        <div class="sonar-wave wave-3"></div>
        <div class="center-point"></div>
      </div>
    `,
    iconSize: [400, 400],
    iconAnchor: [200, 200],
  });
}

/**
 * Geospatial Tactical Radar: Pins a Doppler scanning layer directly to the user's coordinates.
 * Stays georeferenced to the map so dragging/zooming maintains exact anchor to the city.
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
  } else {
    const radarIcon = createRadarIcon();
    state.radarMarker = L.marker([targetLat, targetLon], {
      icon: radarIcon,
      interactive: false,
      keyboard: false,
      zIndexOffset: -100, // Sits under hazard badges and user beacon, over map tiles
    }).addTo(state.map);
  }

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
const initRadarSweep = initRadar;
window.initRadar = initRadar;
window.initRadarSweep = initRadar;

function updateGeospatialLayer(locationData, alertsList, synopticOverlays) {
  if (!state.map) return;

  state.currentAlerts = alertsList || [];
  state.alertMarkersMap = new Map();

  let centerLat = 22.5726;
  let centerLon = 88.3639; // Default/fallback
  let hasValidCoords = false;

  // 1. Task 1: Re-center map and flyTo user coordinates when available in ChatResponse.location
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
  } else {
    initRadar(centerLat, centerLon);
  }

  if (hasValidCoords) {
    // Fly to user coordinates at zoom level 10 (Surgical GPS Centering)
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
      <div class="world-monitor-popup" style="font-family:'JetBrains Mono',monospace; min-width:220px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; border-bottom:1px solid rgba(0,210,255,0.3); padding-bottom:4px;">
          <span style="color:#00D2FF; font-weight:800; font-size:11px;">[USER BEACON]</span>
          <span style="font-weight:800; font-size:9px; background:#001a2c; border:1px solid #00D2FF; color:#00D2FF; padding:1px 5px; border-radius:2px;">
            RADAR GPS // FIXED
          </span>
        </div>
        <div style="color:#ffffff; font-weight:700; font-size:12px; margin-bottom:4px;">
          ${escapeHtml(locName)}
        </div>
        <div style="font-size:10px; color:#7fa886; border-top:1px dashed rgba(255,255,255,0.12); padding-top:4px;">
          COORDINATES: ${centerLat.toFixed(4)}°N, ${centerLon.toFixed(4)}°E
        </div>
      </div>
    `);
  }

  // 2. Task 2: Synoptic Heatmap Visualization (Yellow to Red Heat Map over Bay of Bengal / Arabian Sea)
  if (state.synopticLayerGroup) {
    state.synopticLayerGroup.clearLayers();
  }

  const overlays = synopticOverlays || [];
  overlays.forEach((overlay, idx) => {
    if (!overlay.bounds || overlay.bounds.length < 2) return;

    // Tactical Bounding Box across the water body
    const boundsRect = L.rectangle(overlay.bounds, {
      className: 'synoptic-bound-rect',
      weight: 1.5,
      color: '#FF3131',
      dashArray: '6, 6',
      fillColor: '#FF5722',
      fillOpacity: 0.05,
    });

    const overlayCenter = (overlay.center && overlay.center.length === 2)
      ? overlay.center
      : [
        (overlay.bounds[0][0] + overlay.bounds[1][0]) / 2,
        (overlay.bounds[0][1] + overlay.bounds[1][1]) / 2,
      ];

    // Radial Heatmap Effect: Large semi-transparent circle with Yellow-to-Red gradient (Heat/Dust style)
    const heatAuraIcon = L.divIcon({
      className: 'synoptic-svg-wrap',
      html: `
        <svg width="440" height="440" viewBox="0 0 440 440" class="synoptic-svg-aura" style="margin-left:-220px; margin-top:-220px;">
          <defs>
            <radialGradient id="heatAuraGrad_${idx}" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#FF1E1E" stop-opacity="0.65" />
              <stop offset="26%" stop-color="#FF5722" stop-opacity="0.45" />
              <stop offset="52%" stop-color="#FFA500" stop-opacity="0.25" />
              <stop offset="78%" stop-color="#FFEA00" stop-opacity="0.12" />
              <stop offset="100%" stop-color="#FFEA00" stop-opacity="0" />
            </radialGradient>
          </defs>
          <!-- Thermal Heatmap Gradient Field -->
          <circle cx="220" cy="220" r="210" fill="url(#heatAuraGrad_${idx})" />
          <!-- Outer Tropospheric Isobars -->
          <circle cx="220" cy="220" r="150" stroke="#FFA500" stroke-width="1.5" stroke-dasharray="8,6" fill="none" class="aura-rotate-slow" opacity="0.65" />
          <!-- Mid-Level Cyclonic Circulation Ring -->
          <circle cx="220" cy="220" r="95" stroke="#FF5722" stroke-width="1.8" stroke-dasharray="6,4" fill="none" class="aura-rotate-slow" opacity="0.8" />
          <!-- Central Low-Pressure Eye Core -->
          <circle cx="220" cy="220" r="40" stroke="#FF1E1E" stroke-width="2" fill="#FF1E1E" fill-opacity="0.45" class="aura-pulse-glow" />
          <text x="220" y="224" text-anchor="middle" fill="#FFFFFF" font-family="'JetBrains Mono',monospace" font-size="9" font-weight="800" letter-spacing="0.5">
            [${escapeHtml((overlay.type || 'LOW-PRESSURE').toUpperCase())}]
          </text>
        </svg>
      `,
      iconSize: [0, 0],
      iconAnchor: [0, 0],
    });

    const auraMarker = L.marker(overlayCenter, {
      icon: heatAuraIcon,
      interactive: true,
      zIndexOffset: 100,
    });

    const popupContent = `
      <div class="world-monitor-popup" style="font-family:'JetBrains Mono',monospace; min-width:280px; max-width:320px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; border-bottom:1px solid #FF3131; padding-bottom:5px;">
          <span style="color:#FF3131; font-weight:800; font-size:11px;">[SYNOPTIC SYSTEM OVERLAY]</span>
          <span style="font-weight:800; font-size:9px; background:#160707; border:1px solid #FF3131; color:#FFEA00; padding:2px 6px; border-radius:2px;">
            ${escapeHtml((overlay.type || 'LOW-PRESSURE').toUpperCase())}
          </span>
        </div>
        <div style="color:#ffffff; font-weight:700; font-size:12.5px; margin-bottom:5px; line-height:1.35;">
          ${escapeHtml(overlay.name || 'Synoptic Weather System')}
        </div>
        <div style="color:#cbebd0; font-size:10.5px; line-height:1.45; margin-bottom:8px;">
          ${escapeHtml(overlay.description || 'System influence area over oceanic basin.')}
        </div>
        <div style="display:flex; justify-content:space-between; font-size:9px; color:#7fa886; border-top:1px dashed rgba(255,255,255,0.12); padding-top:4px;">
          <span>GEO: [[${overlay.bounds[0].join(', ')}], [${overlay.bounds[1].join(', ')}]]</span>
          <span style="color:#FFEA00; font-weight:700;">SEV: ${escapeHtml((overlay.severity || 'HIGH').toUpperCase())}</span>
        </div>
      </div>
    `;

    boundsRect.bindPopup(popupContent);
    auraMarker.bindPopup(popupContent);

    state.synopticLayerGroup.addLayer(boundsRect);
    state.synopticLayerGroup.addLayer(auraMarker);
  });

  // 3. Hazard Overlay: Draw hazards with visual distinction (Live Neon vs Ghostly Historical)
  renderHazardMarkers(alertsList, centerLat, centerLon);
}

/**
 * Renders tactical radar hazard markers into state.hazardLayerGroup.
 * Distinguishes Live/Current hazards (bright neon red/orange, pulsing animation)
 * from Historical records (dull/ghostly slate-cyan, 35% opacity, dashed border).
 */
function renderHazardMarkers(alertsList, centerLat = 22.5726, centerLon = 88.3639) {
  if (!state.map) return;
  if (state.hazardLayerGroup) {
    state.hazardLayerGroup.clearLayers();
  }
  state.alertMarkersMap = new Map();

  const alerts = alertsList || [];
  alerts.forEach((alert, index) => {
    const isHistorical = Boolean(alert.is_historical);
    const sev = (alert.severity || '').toLowerCase();

    // Visual Distinction: Live vs Ghostly Historical
    let markerColor = '#FFAC1C'; // Orange default
    let pulseClass = 'pulsing-marker pulsing-marker-orange';
    let radius = 16;
    let fillOpacity = 0.55;
    let opacity = 1.0;
    let weight = 2;

    if (isHistorical) {
      markerColor = '#8892b0';
      pulseClass = 'historical-hazard-marker';
      radius = 10;
      fillOpacity = 0.35;
      opacity = 0.45;
      weight = 1.2;
    } else {
      if (sev.includes('high') || sev.includes('extreme') || sev.includes('severe')) {
        markerColor = '#FF3131'; // Red for High/Extreme
        pulseClass = 'pulsing-marker pulsing-marker-red';
      } else if (sev.includes('moderate')) {
        markerColor = '#FFAC1C';
        pulseClass = 'pulsing-marker pulsing-marker-orange';
      }
    }

    // Precise Alert Geolocation: Prioritize alert.latitude and alert.longitude
    let alertLat = null;
    let alertLon = null;

    if (alert.latitude != null && alert.longitude != null && !isNaN(Number(alert.latitude)) && !isNaN(Number(alert.longitude))) {
      alertLat = parseFloat(alert.latitude);
      alertLon = parseFloat(alert.longitude);
    } else {
      const angle = (index * (2 * Math.PI / Math.max(alerts.length, 1))) + 0.3;
      const distance = index === 0 ? 0.0 : (0.04 + (index * 0.02));
      alertLat = centerLat + (Math.sin(angle) * distance);
      alertLon = centerLon + (Math.cos(angle) * distance);
    }

    const hazardCircle = L.circleMarker([alertLat, alertLon], {
      radius: radius,
      color: markerColor,
      fillColor: markerColor,
      fillOpacity: fillOpacity,
      opacity: opacity,
      weight: weight,
      className: pulseClass,
    });

    const sourceLabel = escapeHtml(alert.source || 'IMD');
    const titleLabel = escapeHtml(alert.title || 'Meteorological Hazard');
    const descLabel = escapeHtml(alert.description || 'Hazard condition reported in official bulletin.');
    const sevLabel = (alert.severity || 'ALERT').toUpperCase();
    const coordStr = `${alertLat.toFixed(2)}°, ${alertLon.toFixed(2)}°`;
    const tagColor = isHistorical ? '#8892b0' : markerColor;
    const statusFooter = isHistorical ? 'HISTORICAL RECORD // USGS ARCHIVE' : 'WORLD MONITOR // ACTIVE';

    let timeBadge = '';
    if (alert.occurred_at) {
      try {
        const d = new Date(alert.occurred_at);
        const timeStr = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
        timeBadge = `<div style="font-size:9.5px; color:#8892b0; margin-bottom:5px;">TIMESTAMP: ${escapeHtml(timeStr)}</div>`;
      } catch (e) {
        timeBadge = `<div style="font-size:9.5px; color:#8892b0; margin-bottom:5px;">TIMESTAMP: ${escapeHtml(String(alert.occurred_at).slice(0, 19))}</div>`;
      }
    }

    const popupHtml = `
      <div class="world-monitor-popup" style="font-family:'JetBrains Mono',monospace; min-width:240px; max-width:300px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.18); padding-bottom:5px;">
          <span style="color:${tagColor}; font-weight:800; font-size:11px; letter-spacing:0.5px;">[${isHistorical ? 'HISTORICAL' : sevLabel}]</span>
          <span style="font-weight:800; font-size:10px; background:#000000; border:1px solid ${tagColor}; color:#ffffff; padding:2px 6px; border-radius:2px;">
            <strong>SOURCE: ${sourceLabel}</strong>
          </span>
        </div>
        <div style="color:#ffffff; font-weight:700; font-size:12px; margin-bottom:5px; line-height:1.35;">
          ${titleLabel}
        </div>
        ${timeBadge}
        <div style="color:#cbebd0; font-size:10.5px; line-height:1.4; margin-bottom:7px;">
          ${descLabel}
        </div>
        <div style="display:flex; justify-content:space-between; font-size:9px; color:#7fa886; border-top:1px dashed rgba(255,255,255,0.12); padding-top:4px;">
          <span>GEO: ${coordStr}</span>
          <span style="color:${tagColor}; font-weight:700;">${statusFooter}</span>
        </div>
      </div>
    `;

    hazardCircle.bindPopup(popupHtml);
    state.alertMarkersMap.set(alert, hazardCircle);

    if (state.hazardLayerGroup) {
      state.hazardLayerGroup.addLayer(hazardCircle);
    }
  });
}

// Alias updateMap for backwards compatibility
const updateMap = updateGeospatialLayer;

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

// ── 3. Ticker Tape Binding (Synoptic Overview) ───────────────────────────────
function bindTickerTape(botReply) {
  if (!botReply || !elements.tickerTrack) return;

  // Task 2: Bind the first sentence of bot_reply (Synoptic Overview) to the top marquee
  let synopticText = '';

  // 1. Look for explicit Synoptic Status section or Low Pressure / Nowcast sentence
  const synopticMatch = botReply.match(/SYNOPTIC (?:STATUS|OVERVIEW)[:\s*#]+([^\n#]+)/i);
  if (synopticMatch && synopticMatch[1] && synopticMatch[1].trim().length > 10) {
    synopticText = synopticMatch[1].trim();
  } else {
    const lowPressureMatch = botReply.match(/([^.\n]*?(?:low[- ]pressure|depression|trough|nowcast)[^.\n]*?[.!?])/i);
    if (lowPressureMatch && lowPressureMatch[1] && lowPressureMatch[1].trim().length > 15) {
      synopticText = lowPressureMatch[1].trim();
    }
  }

  // 2. Fallback to the first sentence of bot_reply
  if (!synopticText) {
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
  synopticText = synopticText
    .replace(/^SYNOPTIC\s+(?:STATUS|OVERVIEW)[:\s-]*/i, '')
    .replace(/[*_`>~#]/g, '')
    .replace(/^[-\u2022]\s+/, '')
    .replace(/\s+/g, ' ')
    .trim();

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

// ── 4. Live Telemetry Widgets (Big Digits) ───────────────────────────────────
function bindTelemetryWidgets(weatherData, alertsData) {
  const current = weatherData?.current;

  // Task 2: Big Digits - Map weather.current.temperature and humidity to large widgets
  // 1. Digital Temperature Display (Big Digits)
  if (current && current.temperature != null) {
    elements.telemetryTemp.textContent = `${Number(current.temperature).toFixed(1)}°C`;
    const feelsLike = current.feels_like != null ? `FEELS LIKE ${Number(current.feels_like).toFixed(1)}°C` : 'REAL-TIME SENSOR';
    elements.telemetryTempSub.textContent = feelsLike;
  } else {
    elements.telemetryTemp.textContent = '--°C';
    elements.telemetryTempSub.textContent = 'AWAITING TELEMETRY';
  }

  // 2. Humidity Gauge (Big Digits & Visual Ratio Bar)
  if (current && current.humidity != null) {
    const humidVal = Math.round(current.humidity);
    elements.telemetryHumidity.textContent = `${humidVal}%`;
    elements.telemetryHumiditySub.textContent = 'RELATIVE HUMIDITY';
    if (elements.humidityBarFill) {
      elements.humidityBarFill.style.width = `${Math.min(100, Math.max(0, humidVal))}%`;
    }
  } else {
    elements.telemetryHumidity.textContent = '--%';
    elements.telemetryHumiditySub.textContent = 'SENSOR OFFLINE';
    if (elements.humidityBarFill) {
      elements.humidityBarFill.style.width = '0%';
    }
  }

  // 3. Wind Velocity widget
  if (current && current.wind_speed != null) {
    elements.telemetryWind.textContent = `${Number(current.wind_speed).toFixed(1)} km/h`;
    elements.telemetryWindSub.textContent = 'SURFACE VELOCITY';
  } else {
    elements.telemetryWind.textContent = '-- km/h';
    elements.telemetryWindSub.textContent = 'AWAITING ANEMOMETER';
  }

  // 4. Barometric / Hazards tracker widget
  const alertCount = (alertsData || []).length;
  elements.telemetryAlertsCount.textContent = `${alertCount} ACTIVE`;
  if (alertCount > 0) {
    elements.telemetryAlertsCount.style.color = '#FF3131';
    elements.telemetryBaroSub.textContent = 'OFFICIAL HAZARDS TRACKED';
  } else {
    elements.telemetryAlertsCount.style.color = '#00FF41';
    elements.telemetryBaroSub.textContent = 'NO ACTIVE WARNINGS';
  }
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
        elements.crisisBanner.innerHTML = '<span>⚠️ CRITICAL METEOROLOGICAL ALERT DETECTED — HIGH/EXTREME SEVERITY HAZARDS ACTIVE</span><span style="font-size: 10px; opacity: 0.85;">REVIEW TACTICAL RADAR HAZARD OVERLAY IMMEDIATELY</span>';
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

function appendSystemLoading() {
  const loadingEntry = document.createElement('div');
  loadingEntry.className = 'message-entry system-loading';
  loadingEntry.id = 'systemLoadingIndicator';

  const spinner = document.createElement('div');
  spinner.className = 'system-spinner';

  const label = document.createElement('span');
  label.textContent = 'QUERYING RAG BRAIN & SATELLITE RADAR...';

  loadingEntry.append(spinner, label);
  elements.chatStream.appendChild(loadingEntry);
  loadingEntry.scrollIntoView({ behavior: 'smooth', block: 'end' });
  return loadingEntry;
}

function appendBotMessage(response) {
  const msgEntry = document.createElement('div');
  msgEntry.className = 'message-entry bot-message';

  const prefix = document.createElement('span');
  prefix.className = 'message-prefix';
  prefix.textContent = 'METEOROLOGICAL_INTELLIGENCE';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  // Render response.bot_reply using marked.js parser
  const rawReply = response.bot_reply || 'No meteorological telemetry returned.';
  if (typeof marked !== 'undefined' && marked.parse) {
    contentDiv.innerHTML = marked.parse(rawReply);
  } else {
    contentDiv.textContent = rawReply;
  }

  msgEntry.append(prefix, contentDiv);

  // Audio Playback Attachment if response.audio_url or audio_base64 exists
  const audioSrc = response.audio_base64 || response.audio_url;
  if (audioSrc) {
    const audioWrap = document.createElement('div');
    audioWrap.className = 'audio-player-wrap';

    const audioHeader = document.createElement('div');
    audioHeader.className = 'audio-player-header';
    audioHeader.innerHTML = `
      <span class="audio-player-tag">SYS_VOICE // NEURAL_AUDIO_STREAM</span>
      <span class="audio-status-pill">READY</span>
    `;
    audioWrap.appendChild(audioHeader);

    const audioEl = document.createElement('audio');
    audioEl.controls = true;
    audioEl.preload = 'auto';
    audioEl.src = audioSrc;

    // Task 2: Force browser re-fetch/handshake via audio.load()
    audioEl.load();

    // Event listener to log SYS_VOICE > PLAYING in terminal console
    audioEl.addEventListener('play', () => {
      console.log('SYS_VOICE > PLAYING');
      const pill = audioWrap.querySelector('.audio-status-pill');
      if (pill) {
        pill.textContent = 'PLAYING';
        pill.className = 'audio-status-pill is-playing';
      }
    });

    audioEl.addEventListener('pause', () => {
      console.log('SYS_VOICE > PAUSED');
      const pill = audioWrap.querySelector('.audio-status-pill');
      if (pill) {
        pill.textContent = 'PAUSED';
        pill.className = 'audio-status-pill is-paused';
      }
    });

    audioEl.addEventListener('ended', () => {
      console.log('SYS_VOICE > ENDED');
      const pill = audioWrap.querySelector('.audio-status-pill');
      if (pill) {
        pill.textContent = 'ENDED';
        pill.className = 'audio-status-pill';
      }
    });

    audioWrap.appendChild(audioEl);
    msgEntry.appendChild(audioWrap);
  }

  // Task 3: Render de-duplicated response.sources in a clean monospace badge row
  const rawSources = response.sources || [];
  if (rawSources.length > 0) {
    const badgeRow = document.createElement('div');
    badgeRow.className = 'source-badge-row';

    const labelSpan = document.createElement('span');
    labelSpan.className = 'source-badge-label';
    labelSpan.textContent = 'SOURCES:';
    badgeRow.appendChild(labelSpan);

    // De-duplication map keyed by normalized (source name + page)
    const uniqueSources = new Map();
    rawSources.forEach((src) => {
      const srcName = (src.source || 'Official IMD Document').trim();
      const normKey = srcName.toLowerCase();

      if (!uniqueSources.has(normKey)) {
        uniqueSources.set(normKey, {
          source: srcName,
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

    uniqueSources.forEach((entry) => {
      // Determine page number and file path for full MoES transparency
      let pageNum = 'Page 1';
      const pageMatch = (entry.source + ' ' + entry.content).match(/(?:page|p\.)\s*(\d+)/i);
      if (pageMatch) {
        pageNum = `Page ${pageMatch[1]}`;
      } else if (entry.count > 1) {
        pageNum = `Pages 1-${entry.count}`;
      }

      let docFilename = 'national_disaster_management_plan.pdf';
      const sLower = entry.source.toLowerCase();
      if (sLower.includes('bulletin') || sLower.includes('nowcast')) {
        docFilename = 'national_bulletin.pdf';
      } else if (sLower.includes('source_registry')) {
        docFilename = 'source_registry.json';
      }
      const docUrl = `/data/${docFilename}`;

      const badgeWrap = document.createElement('div');
      badgeWrap.style.display = 'inline-flex';
      badgeWrap.style.alignItems = 'center';
      badgeWrap.style.gap = '2px';

      const badge = document.createElement('button');
      badge.type = 'button';
      badge.className = 'wm-source-badge';

      let tagLabel = 'DOC';
      if (sLower.includes('imd')) tagLabel = 'IMD';
      else if (sLower.includes('usgs')) tagLabel = 'USGS';
      else if (sLower.includes('incois')) tagLabel = 'INCOIS';
      else if (sLower.includes('ndmp')) tagLabel = 'NDMP';

      const countSuffix = entry.count > 1 ? ` (${entry.count}x)` : '';
      badge.innerHTML = `<span class="badge-tag">[${tagLabel}]</span> ${escapeHtml(entry.source)} <span style="color:#00FF41; font-weight:700;">(${pageNum})</span>${countSuffix}`;
      badge.title = `Click to inspect document excerpt (${entry.count} references merged)`;

      badge.addEventListener('click', () => {
        openSourceModal({
          source: entry.source,
          content: entry.content,
          score: entry.score,
          page: pageNum,
          docUrl: docUrl,
        });
      });

      const docLink = document.createElement('a');
      docLink.href = docUrl;
      docLink.target = '_blank';
      docLink.rel = 'noopener';
      docLink.className = 'wm-source-view-link';
      docLink.style.fontSize = '9px';
      docLink.style.color = '#00FF41';
      docLink.style.textDecoration = 'underline';
      docLink.style.marginLeft = '3px';
      docLink.textContent = '[VIEW DOC]';
      docLink.title = `Open ${docFilename} in browser`;

      badgeWrap.appendChild(badge);
      badgeWrap.appendChild(docLink);
      badgeRow.appendChild(badgeWrap);
    });

    msgEntry.appendChild(badgeRow);
  }

  // De-duplicated response.alerts in clean monospace hazard row
  const rawAlerts = response.alerts || [];
  if (rawAlerts.length > 0) {
    const hazardRow = document.createElement('div');
    hazardRow.className = 'source-badge-row';
    hazardRow.style.marginTop = '4px';

    const hLabel = document.createElement('span');
    hLabel.className = 'source-badge-label';
    hLabel.textContent = 'RADAR HAZARDS:';
    hazardRow.appendChild(hLabel);

    const uniqueAlerts = new Map();
    rawAlerts.forEach((alert) => {
      const key = `${(alert.title || '').trim()}::${(alert.source || '').trim()}`.toLowerCase();
      if (!uniqueAlerts.has(key)) {
        uniqueAlerts.set(key, alert);
      }
    });

    uniqueAlerts.forEach((alert) => {
      const isHigh = (alert.severity || '').toLowerCase().includes('high');
      const badge = document.createElement('button');
      badge.type = 'button';
      badge.className = 'wm-source-badge wm-hazard-badge';
      const locText = alert.latitude != null ? ` [${alert.latitude.toFixed(1)}°, ${alert.longitude.toFixed(1)}°]` : '';
      badge.innerHTML = `<span style="color:${isHigh ? '#FF3131' : '#FFAC1C'}; font-weight:800;">!</span> [${escapeHtml(alert.source || 'HAZARD')}] ${escapeHtml(alert.title || 'Alert')}${locText} &gt;&gt; FLYTO`;
      badge.title = 'Click to fly tactical radar to this hazard location';

      badge.addEventListener('click', () => {
        flyToHazard(alert);
      });

      hazardRow.appendChild(badge);
    });

    msgEntry.appendChild(hazardRow);
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
  elements.sourceModalTitle.textContent = `SOURCE INSPECTION // ${sourceItem.source || 'BULLETIN'}`;
  elements.sourceModalContent.textContent = sourceItem.content || 'Excerpt text unavailable in current index.';

  const scoreText = sourceItem.score != null ? `VECTOR_RELEVANCE_SCORE: ${Number(sourceItem.score).toFixed(4)}` : 'MATCH: DIRECT RETRIEVAL';
  const pageText = sourceItem.page ? `PAGE: ${sourceItem.page} | ` : '';
  elements.sourceModalMeta.textContent = `CLASSIFICATION: OFFICIAL INTELLIGENCE | ${pageText}${scoreText}`;

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

async function executeChatRequest(queryText) {
  if (!queryText || state.isExecuting) return;

  state.isExecuting = true;
  elements.executeBtn.disabled = true;
  elements.queryInput.disabled = true;

  appendUserMessage(queryText);
  elements.queryInput.value = '';

  const loadingIndicator = appendSystemLoading();

  // Construct request payload strictly matching ChatRequest schema
  const payload = {
    query: queryText,
    language: elements.languageSelect ? elements.languageSelect.value : 'en',
    channel: state.isVoiceMode ? 'voice' : 'web',
    location: buildLocationPayload(),
  };

  // Reset voice mode flag after payload prepared
  state.isVoiceMode = false;

  try {
    // Relative path /chat ensures it works regardless of backend port
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

    if (data.detected_language && elements.languageSelect && elements.languageSelect.value === 'auto') {
      const hasOpt = Array.from(elements.languageSelect.options).some(o => o.value === data.detected_language);
      if (hasOpt) {
        elements.languageSelect.value = data.detected_language;
        applyLocalization(data.detected_language);
      }
    }

    // Cache telemetry state for temporal analysis and emergency triggers
    state.lastWeatherData = data.weather;
    state.currentLocation = data.location;
    state.historyData = data.history_data || [];

    // 1. Render Markdown reply & Source Pills
    appendBotMessage(data);

    // 2. Map the first paragraph to scrolling Ticker Tape
    bindTickerTape(data.bot_reply);

    // 3. Bind Telemetry Widgets
    bindTelemetryWidgets(data.weather, data.alerts);

    // 4. Update Geospatial Radar (Leaflet.js)
    state.currentOverlays = data.synoptic_overlays || [];
    updateGeospatialLayer(data.location, data.alerts, data.synoptic_overlays);

    // 5. Emergency UI State (crisis-mode: alerts + temp > 45°C + wind > 75km/h)
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
    elements.executeBtn.disabled = false;
    elements.queryInput.disabled = false;
    elements.queryInput.focus();
  }
}

// ── 9. Form Submission & Quick Prompts ───────────────────────────────────────
if (elements.commandForm) {
  elements.commandForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = elements.queryInput.value.trim();
    if (query) executeChatRequest(query);
  });
}

document.querySelectorAll('.quick-prompt-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const prompt = btn.getAttribute('data-prompt');
    if (prompt) {
      elements.queryInput.value = prompt;
      executeChatRequest(prompt);
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
  elements.manualLocationInput.addEventListener('input', (e) => {
    state.manualLocationText = e.target.value.trim();
    if (state.manualLocationText) {
      elements.locationSummaryText.textContent = `LOC: ${state.manualLocationText.toUpperCase()}`;
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

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstart = () => {
        elements.voiceBtn.classList.add('is-recording');
        elements.voiceBtn.setAttribute('title', 'Listening... Click again to process');
        state.isVoiceMode = true;

        // Visual indicator: SYS_VOICE > LISTENING...
        if (voiceIndicatorEl) voiceIndicatorEl.remove();
        voiceIndicatorEl = document.createElement('div');
        voiceIndicatorEl.className = 'message-entry system-loading';
        voiceIndicatorEl.innerHTML = `
          <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#FF3131; box-shadow:0 0 10px #FF3131; margin-right:8px; animation: mic-blink 0.8s infinite;"></span>
          <span style="color:#FF3131; font-weight:700; letter-spacing:0.5px;">SYS_VOICE &gt; LISTENING...</span>
        `;
        elements.chatStream.appendChild(voiceIndicatorEl);
        voiceIndicatorEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
      };

      mediaRecorder.onstop = async () => {
        elements.voiceBtn.classList.remove('is-recording');
        elements.voiceBtn.setAttribute('title', 'Voice Input (Tap to record)');
        stream.getTracks().forEach((track) => track.stop());

        if (audioChunks.length === 0) {
          if (voiceIndicatorEl) {
            voiceIndicatorEl.remove();
            voiceIndicatorEl = null;
          }
          return;
        }

        // Switch indicator: SYS_VOICE > PROCESSING...
        if (voiceIndicatorEl) {
          voiceIndicatorEl.innerHTML = `
            <div class="system-spinner"></div>
            <span style="color:var(--terminal-green); font-weight:700; letter-spacing:0.5px;">SYS_VOICE &gt; PROCESSING...</span>
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

          // 1. Display the recognized user query in the chat stream & input field
          const userText = data.transcribed_query || 'Voice query';
          appendUserMessage(userText);
          elements.queryInput.value = userText;

          // Realign output language selector & localization using Linguistic Passport (locked_language_code)
          const lockedLang = data.locked_language_code || data.detected_language;
          if (lockedLang && elements.languageSelect) {
            const hasOpt = Array.from(elements.languageSelect.options).some(o => o.value === lockedLang);
            if (hasOpt) {
              elements.languageSelect.value = lockedLang;
              applyLocalization(lockedLang);
            }
          }


          // 2. Cache telemetry state for temporal analysis and emergency triggers
          state.lastWeatherData = data.weather;
          state.currentLocation = data.location;
          state.historyData = data.history_data || [];

          // 3. Render Markdown reply & Source Pills (with embedded audio player)
          const botMsgEl = appendBotMessage(data);

          // 4. Map the first paragraph to scrolling Ticker Tape
          bindTickerTape(data.bot_reply);

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
          const rawErr = err.message || 'Please type query.';
          const displayErr = rawErr.startsWith('SYS_VOICE >') ? rawErr : `Voice processing failed: ${rawErr}`;
          errMsg.innerHTML = `
            <span class="message-prefix" style="color:var(--terminal-red);">SYS_VOICE &gt; ERROR</span>
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
  try {
    const res = await fetch('/health', { cache: 'no-store' });
    if (!res.ok) throw new Error();
    if (elements.systemStatusText) elements.systemStatusText.textContent = 'SYS_ONLINE';
    if (elements.systemIndicator) {
      elements.systemIndicator.style.backgroundColor = '#00FF41';
      elements.systemIndicator.style.boxShadow = '0 0 8px #00FF41';
    }
  } catch {
    if (elements.systemStatusText) elements.systemStatusText.textContent = 'SYS_OFFLINE';
    if (elements.systemIndicator) {
      elements.systemIndicator.style.backgroundColor = '#FF3131';
      elements.systemIndicator.style.boxShadow = '0 0 8px #FF3131';
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

    // 2. Instantly populate Big Digits Telemetry Widgets (Temperature, Humidity, Wind, Active Hazards)
    bindTelemetryWidgets(data.weather, data.alerts);

    // 3. Instantly populate Top Marquee Ticker Tape with Synoptic Overview
    bindTickerTape(data.bot_reply);

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
    badge.textContent = `RADAR: FILTERING [${interval.toUpperCase()}]...`;
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
      const histCount = hazards.filter((h) => h.is_historical).length;
      badge.textContent = `RADAR: ${hazards.length} HAZARDS (${histCount} HISTORICAL) [${interval.toUpperCase()}]`;
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
      } else {
        el.textContent = translated;
      }
    }
  });
}

if (elements.languageSelect) {
  elements.languageSelect.addEventListener('change', (e) => {
    applyLocalization(e.target.value);
  });
}

function initializeTerminal() {
  if (state.isInitialized) return;
  state.isInitialized = true;

  initMap();
  initIntervalButtons();
  setupVoiceInput();
  checkBackendHealth();
  applyLocalization(elements.languageSelect ? elements.languageSelect.value : 'en');

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
