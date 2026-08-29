const state = {
  locationMode: "gps",
  gpsLocation: null,
  isSending: false,
  isVoiceMode: false,  // true while mic is active → sets channel:"voice"
};

const elements = {
  chatForm: document.querySelector("#chatForm"),
  conversation: document.querySelector("#conversation"),
  queryInput: document.querySelector("#queryInput"),
  languageSelect: document.querySelector("#languageSelect"),
  sendButton: document.querySelector("#sendButton"),
  voiceButton: document.querySelector("#voiceButton"),
  locationButton: document.querySelector("#locationButton"),
  locationButtonLabel: document.querySelector("#locationButtonLabel"),
  locationPanel: document.querySelector("#locationPanel"),
  closeLocationButton: document.querySelector("#closeLocationButton"),
  locationSummary: document.querySelector("#locationSummary"),
  gpsModeButton: document.querySelector("#gpsModeButton"),
  manualModeButton: document.querySelector("#manualModeButton"),
  gpsSection: document.querySelector("#gpsSection"),
  manualSection: document.querySelector("#manualSection"),
  gpsButton: document.querySelector("#gpsButton"),
  gpsFeedback: document.querySelector("#gpsFeedback"),
  manualLocation: document.querySelector("#manualLocation"),
  connectionStatus: document.querySelector("#connectionStatus"),
  themeToggle: document.querySelector("#themeToggle"),
  themeIcon: document.querySelector("#themeIcon"),
  userMessageTemplate: document.querySelector("#userMessageTemplate"),
  assistantMessageTemplate: document.querySelector("#assistantMessageTemplate"),
};

function autoResize() {
  elements.queryInput.style.height = "auto";
  elements.queryInput.style.height = `${Math.min(elements.queryInput.scrollHeight, 125)}px`;
}

function setLocationMode(mode) {
  state.locationMode = mode;
  const manual = mode === "manual";
  elements.gpsModeButton.classList.toggle("is-active", !manual);
  elements.manualModeButton.classList.toggle("is-active", manual);
  elements.gpsSection.hidden = manual;
  elements.manualSection.classList.toggle("is-visible", manual);

  if (manual) {
    elements.manualLocation.focus();
  }
}

function toggleLocationPanel(forceOpen) {
  const shouldOpen = forceOpen ?? !elements.locationPanel.classList.contains("is-open");
  elements.locationPanel.classList.toggle("is-open", shouldOpen);
  elements.locationButton.setAttribute("aria-expanded", String(shouldOpen));
}

function updateLocationLabel() {
  if (state.locationMode === "gps" && state.gpsLocation) {
    const { latitude, longitude } = state.gpsLocation;
    const shortCoordinates = `${latitude.toFixed(3)}, ${longitude.toFixed(3)}`;
    elements.locationSummary.textContent = `Using device coordinates: ${shortCoordinates}`;
    elements.locationButtonLabel.textContent = "GPS active";
    return;
  }

  const manualText = elements.manualLocation.value.trim();
  if (state.locationMode === "manual" && manualText) {
    elements.locationSummary.textContent = `Using manual location: ${manualText}`;
    elements.locationButtonLabel.textContent = "Manual location";
    return;
  }

  elements.locationSummary.textContent = "Choose GPS or enter a location.";
  elements.locationButtonLabel.textContent = "Location";
}

function requestGpsLocation() {
  if (!navigator.geolocation) {
    showGpsError("This browser cannot access device location. Enter a location manually instead.");
    return;
  }

  elements.gpsButton.disabled = true;
  elements.gpsButton.textContent = "Finding your location…";
  elements.gpsFeedback.classList.remove("is-error");
  elements.gpsFeedback.textContent = "Allow location access if your browser asks.";

  navigator.geolocation.getCurrentPosition(
    (position) => {
      state.gpsLocation = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      };
      elements.gpsFeedback.textContent = "Location captured. You can now ask a question.";
      elements.gpsButton.disabled = false;
      elements.gpsButton.innerHTML = "<span aria-hidden=\"true\">✓</span> Device location ready";
      updateLocationLabel();
    },
    (error) => {
      const messages = {
        1: "Location permission was denied. Enter a city or PIN code manually instead.",
        2: "Your location is unavailable right now. Enter it manually instead.",
        3: "Location lookup timed out. Try again or enter it manually.",
      };
      showGpsError(messages[error.code] || "Could not get your location. Enter it manually instead.");
      setLocationMode("manual");
      toggleLocationPanel(true);
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
  );
}

function showGpsError(message) {
  elements.gpsFeedback.classList.add("is-error");
  elements.gpsFeedback.textContent = message;
  elements.gpsButton.disabled = false;
  elements.gpsButton.innerHTML = "<span aria-hidden=\"true\">⌖</span> Try device location";
}

function getLocationInput() {
  if (state.locationMode === "gps" && state.gpsLocation) {
    return state.gpsLocation;
  }

  const rawText = elements.manualLocation.value.trim();
  if (rawText) {
    return { raw_text: rawText };
  }
  return null;
}

function appendUserMessage(text) {
  const node = elements.userMessageTemplate.content.firstElementChild.cloneNode(true);
  node.querySelector("p").textContent = text;
  elements.conversation.append(node);
  node.scrollIntoView({ behavior: "smooth", block: "end" });
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(text);
  const codeSpans = [];

  html = html.replace(/`([^`\n]+)`/g, (_, code) => {
    codeSpans.push(`<code>${code}</code>`);
    return `\u0000${codeSpans.length - 1}\u0000`;
  });
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  );
  html = html.replace(/\*\*([^*\n]+)\*\*|__([^_\n]+)__/g, (_, bold, underscored) => `<strong>${bold || underscored}</strong>`);
  html = html.replace(/(^|[^\*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  html = html.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, "$1<em>$2</em>");
  return html.replace(/\u0000(\d+)\u0000/g, (_, index) => codeSpans[index]);
}

function renderMarkdown(markdown) {
  // Some model responses put section headings after a horizontal rule without
  // line breaks. Normalize those boundaries before applying block formatting.
  const normalized = String(markdown)
    .replace(/\s*---\s*(?=###\s)/g, "\n\n---\n\n")
    .replace(/###\s+\*\*([^*\n]+)\*\*/g, "\n\n### $1\n\n")
    .replace(/([.!?])\s+(?=###\s)/g, "$1\n\n");
  const lines = normalized.split(/\r?\n/);
  const blocks = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push(`<${list.type}>${list.items.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</${list.type}>`);
      list = null;
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }
    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push(`<h${heading[1].length}>${renderInlineMarkdown(heading[2])}</h${heading[1].length}>`);
      continue;
    }
    if (/^(?:---+|\*\*\*+|___+)$/.test(trimmed)) {
      flushParagraph();
      flushList();
      blocks.push("<hr>");
      continue;
    }
    const unordered = trimmed.match(/^[-*+]\s+(.+)$/);
    const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const type = unordered ? "ul" : "ol";
      if (!list || list.type !== type) {
        flushParagraph();
        flushList();
        list = { type, items: [] };
      }
      list.items.push((unordered || ordered)[1]);
      continue;
    }
    flushList();
    paragraph.push(trimmed);
  }
  flushParagraph();
  flushList();
  return blocks.join("");
}

function appendAssistantMessage(response) {
  const node = elements.assistantMessageTemplate.content.firstElementChild.cloneNode(true);
  node.querySelector(".message-content").innerHTML = renderMarkdown(
    response.bot_reply || "No answer was returned.",
  );

  const meta = node.querySelector(".message-meta");
  if (response.location?.city) {
    addMetaPill(meta, response.location.city);
  }
  if (response.weather?.current?.temperature !== null && response.weather?.current?.temperature !== undefined) {
    addMetaPill(meta, `${response.weather.current.temperature}°C now`);
  }
  for (const alert of response.alerts || []) {
    addMetaPill(meta, `${alert.severity}: ${alert.title}`);
  }
  for (const source of response.sources || []) {
    addMetaPill(meta, source.source);
  }

  // Audio playback — populated when channel=="voice" is sent
  if (response.audio_url) {
    const audioWrap = document.createElement("div");
    audioWrap.className = "audio-player";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.autoplay = true;
    audio.src = response.audio_url;
    audioWrap.append(audio);
    node.querySelector(".message-content").after(audioWrap);
  }

  elements.conversation.append(node);
  node.scrollIntoView({ behavior: "smooth", block: "end" });
}

function appendStatusMessage(text, isError = false) {
  const node = document.createElement("article");
  node.className = `message message--assistant ${isError ? "message--error" : "message--loading"}`;
  node.textContent = text;
  elements.conversation.append(node);
  node.scrollIntoView({ behavior: "smooth", block: "end" });
  return node;
}

function addMetaPill(container, text) {
  const pill = document.createElement("span");
  pill.className = "meta-pill";
  pill.textContent = text;
  container.append(pill);
}

function setSending(isSending) {
  state.isSending = isSending;
  elements.sendButton.disabled = isSending;
  elements.queryInput.disabled = isSending;
  elements.sendButton.innerHTML = isSending
    ? "Sending\u2026"
    : `Send <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>`;
}

async function sendChat(event) {
  event.preventDefault();
  if (state.isSending) return;

  const query = elements.queryInput.value.trim();
  const location = getLocationInput();

  if (!query) return;
  if (!location) {
    toggleLocationPanel(true);
    appendStatusMessage("Choose device location or enter a city, district, landmark, or PIN code first.", true);
    return;
  }

  appendUserMessage(query);
  elements.queryInput.value = "";
  autoResize();
  setSending(true);
  const loadingMessage = appendStatusMessage("Checking weather and safety guidance…");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        location,
        language: elements.languageSelect.value,
        channel: state.isVoiceMode ? "voice" : "web",
      }),
    });
    state.isVoiceMode = false;  // reset after each send

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof body.detail === "string" ? body.detail : "The server could not process this request.";
      throw new Error(detail);
    }

    loadingMessage.remove();
    appendAssistantMessage(body);
  } catch (error) {
    loadingMessage.remove();
    appendStatusMessage(error.message || "Could not contact WeatherGPT. Please try again.", true);
  } finally {
    setSending(false);
  }
}

let mediaRecorder = null;
let audioChunks = [];

function setupVoiceInput() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
    setupWebSpeechFallback();
    return;
  }

  elements.voiceButton.addEventListener("click", async () => {
    // Single click while recording → manual stop, transcription fires automatically
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      return;
    }

    let stream, audioCtx, silenceChecker, noSpeechTimer;

    const cleanup = () => {
      clearInterval(silenceChecker);
      clearTimeout(noSpeechTimer);
      if (audioCtx) audioCtx.close().catch(() => {});
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];

      // ── Silence detection via Web Audio API ───────────────────
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      const pcmData = new Uint8Array(analyser.frequencyBinCount);

      let hadSpeech = false;
      let silenceStart = null;

      // Auto-cancel after 4 s if nothing was ever spoken
      noSpeechTimer = setTimeout(() => {
        if (!hadSpeech && mediaRecorder && mediaRecorder.state === "recording") {
          audioChunks = [];   // discard → onstop skips sending
          mediaRecorder.stop();
          appendStatusMessage("No speech detected — tap the mic and speak clearly.", true);
        }
      }, 4000);

      // Poll RMS 10× per second
      silenceChecker = setInterval(() => {
        analyser.getByteTimeDomainData(pcmData);
        let sum = 0;
        for (let i = 0; i < pcmData.length; i++) {
          const v = (pcmData[i] / 128) - 1;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / pcmData.length);

        if (rms > 0.012) {
          // Active speech detected
          hadSpeech = true;
          silenceStart = null;
          clearTimeout(noSpeechTimer);   // speech found — cancel the no-speech guard
        } else if (hadSpeech) {
          // Speech was heard before; now tracking trailing silence
          silenceStart = silenceStart ?? Date.now();
          if (Date.now() - silenceStart >= 2000) {
            // 2 s of silence after speech → auto-stop
            clearInterval(silenceChecker);
            if (mediaRecorder && mediaRecorder.state === "recording") {
              mediaRecorder.stop();
            }
          }
        }
      }, 100);
      // ──────────────────────────────────────────────────────────

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : (MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "");

      mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstart = () => {
        elements.voiceButton.classList.add("is-listening");
        elements.voiceButton.setAttribute("aria-label", "Recording\u2026 Click to stop");
        state.isVoiceMode = true;
      };

      mediaRecorder.onstop = async () => {
        cleanup();
        elements.voiceButton.classList.remove("is-listening");
        elements.voiceButton.setAttribute("aria-label", "Use voice input");

        if (audioChunks.length === 0) return;

        const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
        const formData = new FormData();
        formData.append("file", audioBlob, "voice_input.webm");
        // Only hint language for regional selections; no hint = Whisper auto-detects
        const selectedLang = elements.languageSelect.value;
        if (selectedLang && selectedLang !== "en") {
          formData.append("language", selectedLang);
        }

        const statusMsg = appendStatusMessage("Transcribing audio & detecting language\u2026");

        try {
          const res = await fetch("/voice/transcribe", { method: "POST", body: formData });
          if (!res.ok) throw new Error("Voice transcription failed.");

          const data = await res.json();
          if (data.original_text) {
            elements.queryInput.value = data.original_text;
            autoResize();
            elements.queryInput.focus();
            // Auto-switch dropdown to detected language
            if (data.detected_language && elements.languageSelect.querySelector(`option[value="${data.detected_language}"]`)) {
              elements.languageSelect.value = data.detected_language;
            }
          }
        } catch {
          appendStatusMessage("Could not transcribe speech. Please type your question instead.", true);
        } finally {
          statusMsg.remove();
        }
      };

      mediaRecorder.start();
    } catch {
      cleanup();
      appendStatusMessage("Microphone permission was denied or unavailable.", true);
    }
  });
}

// ── Dark Mode ────────────────────────────────────────────────────────────────
const MOON_SVG = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
const SUN_SVG  = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';

function setTheme(dark) {
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  if (elements.themeIcon) elements.themeIcon.innerHTML = dark ? MOON_SVG : SUN_SVG;
  if (elements.themeToggle) elements.themeToggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  localStorage.setItem("wgpt-theme", dark ? "dark" : "light");
}

function initDarkMode() {
  const saved = localStorage.getItem("wgpt-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(saved ? saved === "dark" : prefersDark);
  if (elements.themeToggle) {
    elements.themeToggle.addEventListener("click", () => {
      setTheme(document.documentElement.getAttribute("data-theme") !== "dark");
    });
  }
}

function setupWebSpeechFallback() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    elements.voiceButton.disabled = true;
    elements.voiceButton.title = "Voice input is not available in this browser";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  const langToBcp47 = {
    en: "en-IN", hi: "hi-IN", bn: "bn-IN", ta: "ta-IN",
    te: "te-IN", mr: "mr-IN", gu: "gu-IN", kn: "kn-IN",
    ml: "ml-IN", ur: "ur-IN",
  };

  elements.voiceButton.addEventListener("click", () => {
    const lang = elements.languageSelect.value || "en";
    recognition.lang = langToBcp47[lang] || "en-IN";
    state.isVoiceMode = true;
    recognition.start();
  });

  recognition.addEventListener("start", () => {
    elements.voiceButton.classList.add("is-listening");
    elements.voiceButton.setAttribute("aria-label", "Listening for your question");
  });
  recognition.addEventListener("end", () => {
    elements.voiceButton.classList.remove("is-listening");
    elements.voiceButton.setAttribute("aria-label", "Use voice input");
  });
  recognition.addEventListener("result", (event) => {
    const transcript = event.results[0][0].transcript;
    elements.queryInput.value = `${elements.queryInput.value} ${transcript}`.trim();
    autoResize();
    elements.queryInput.focus();
  });
  recognition.addEventListener("error", () => {
    state.isVoiceMode = false;
    appendStatusMessage("Voice input was unavailable. Please type your question instead.", true);
  });
}

async function checkConnection() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error();
    elements.connectionStatus.textContent = "Service online";
    elements.connectionStatus.className = "connection-status is-online";
  } catch {
    elements.connectionStatus.textContent = "Service unavailable";
    elements.connectionStatus.className = "connection-status is-offline";
  }
}

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    elements.queryInput.value = button.dataset.prompt;
    autoResize();
    elements.queryInput.focus();
  });
});

elements.chatForm.addEventListener("submit", sendChat);
elements.queryInput.addEventListener("input", autoResize);
elements.locationButton.addEventListener("click", () => toggleLocationPanel());
elements.closeLocationButton.addEventListener("click", () => toggleLocationPanel(false));
elements.gpsModeButton.addEventListener("click", () => setLocationMode("gps"));
elements.manualModeButton.addEventListener("click", () => setLocationMode("manual"));
elements.gpsButton.addEventListener("click", requestGpsLocation);
elements.manualLocation.addEventListener("input", updateLocationLabel);

setLocationMode("gps");
setupVoiceInput();
checkConnection();
initDarkMode();
