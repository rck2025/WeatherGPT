# FRONTEND_CHANGES.md
> **Session:** 2026-08-29 · WeatherGPT Frontend Redesign

---

## Overview

A full frontend redesign of WeatherGPT covering three files:
`frontend/style.css`, `frontend/index.html`, and `frontend/app.js`.
No backend files were modified.

---

## 1. `frontend/style.css` — Full Rewrite

### Design System

| Token | Light | Dark |
|---|---|---|
| `--canvas` | `#f5f7fa` | `#0d1117` |
| `--surface` | `#ffffff` | `#161b27` |
| `--surface-2` | `#eef2f7` | `#1f2437` |
| `--ink` | `#0d1b2a` | `#e2e8f5` |
| `--muted` | `#5a7184` | `#6b7fa8` |
| `--accent` | `#4f6ef7` (indigo) | `#6b8afc` |
| `--warm` | `#f59e0b` (amber) | `#fbbf24` |
| `--danger` | `#e53e3e` | `#fc8181` |

Dark mode tokens live under the `[data-theme="dark"]` selector, enabling an instant, flash-free theme switch with no class juggling.

### Typography
- **Inter** loaded via `@import` from Google Fonts (weights 400–800).
- Replaces the old browser-default `system-ui` stack.
- Heading `letter-spacing: -.045em` and `font-weight: 800` for a premium tight look.

### Layout Changes
- **Location button removed** from the composer bar. The `#locationButton` now lives in the topbar as a pill.
- **Composer bar** is now a single `<form class="composer">` taking the full width — cleaner, simpler.

### Component Highlights

#### Location Pill (topbar)
```css
.location-pill {
  border-radius: var(--r-full);
  background: var(--surface);
  border: 1.5px solid var(--line);
  /* hover: accent border + glow ring */
}
```
Placed in the `<header>` beside the brand logo — mirrors the Rapido/Uber pattern of location as a first-class header element.

#### Messages
- **User bubble:** `background: linear-gradient(135deg, var(--accent), var(--accent-dark))` — indigo gradient, right-aligned, top-right corner square.
- **Assistant card:** Left-aligned, `var(--surface)` background. In dark mode adds `backdrop-filter: blur(14px)` glassmorphism.
- **`WeatherGPT` label strip removed** — the card shape + alignment is the identity.

#### Mic Button
```css
.mic-button {
  width: 40px; height: 40px; border-radius: 50%;
  background: var(--accent-pale);
  color: var(--accent);
}
.mic-button.is-listening {
  background: var(--warm);   /* amber while active */
  color: white;
}
```

Two `.mic-ripple` / `.mic-ripple-2` spans pulse outward as concentric rings while recording:
```css
@keyframes ripple-pulse {
  0%   { transform: scale(1);   opacity: .65; }
  100% { transform: scale(2.4); opacity: 0; }
}
/* mic-ripple-2 has a .55s animation-delay for staggered rings */
```

#### Loading Indicator
The old `font-style: italic` loading message now has a CSS spinner:
```css
.message--loading::before {
  content: '';
  border: 2px solid var(--line);
  border-top-color: var(--accent);
  animation: spin .7s linear infinite;
}
```

#### Animations
| Name | Used on |
|---|---|
| `fadeSlideUp` | Welcome card, every message card entrance |
| `ripple-pulse` | Mic button rings while recording |
| `spin` | Loading message spinner |

---

## 2. `frontend/index.html` — Structural Redesign

### Font Loading
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" />
```

### Topbar — Before vs After

**Before:**
```
[☁ WeatherGPT]                          [● Checking…]
```
Composer bar:
```
[⌖ Location] [textarea ▸ [lang▾] [◉] [Send ↑]]
```

**After:**
```
[☁ WeatherGPT]  [📍 Set location ▾]  ——spacer——  [● Online]  [🌙]
```
Composer bar:
```
[textarea ▸ [lang▾] [🎤] [Send ↑]]
```

The location `id="locationButton"` and `id="locationButtonLabel"` are preserved — only the DOM position and class changed. All existing JS event listeners remain wired correctly.

### Dark Mode Toggle
```html
<button class="theme-toggle" id="themeToggle" type="button">
  <svg id="themeIcon"><!-- moon/sun swapped by JS --></svg>
</button>
```

### Mic Button — Before vs After
**Before:** `<span>◉</span>` text glyph inside `.icon-button`

**After:**
```html
<button class="mic-button" id="voiceButton">
  <svg><!-- microphone path --></svg>
  <span class="mic-ripple" aria-hidden="true"></span>
  <span class="mic-ripple-2" aria-hidden="true"></span>
</button>
```
The two `<span>` elements are animated by CSS when `.is-listening` is applied.

### Assistant Message Template — Label Removed
**Before:**
```html
<article class="message message--assistant">
  <p class="message-label">WeatherGPT</p>  ← removed
  <div class="message-content"></div>
  <div class="message-meta"></div>
</article>
```
**After:** The `<p class="message-label">` strip is gone. The glass card + left-alignment is the identity.

### Cache Busting
`app.js?v=3` — forces browsers to reload after this change.

---

## 3. `frontend/app.js` — Behaviour Upgrades

### Voice Input: Smart Auto-Stop

**Old behaviour:**
- Click mic → start recording
- Click mic again → stop + send (two clicks required)
- No silence detection — recording runs until manually stopped

**New behaviour:**
- Click mic → start recording
- Speak → audio captured
- Stop talking → auto-stops after **2 s of silence**
- Click mic while recording → manual immediate stop
- All paths → transcription fires automatically on stop

#### Implementation: `AudioContext` + `AnalyserNode`
```javascript
audioCtx = new (window.AudioContext || window.webkitAudioContext)();
const analyser = audioCtx.createAnalyser();
analyser.fftSize = 512;
audioCtx.createMediaStreamSource(stream).connect(analyser);
```
RMS energy is polled **10× per second**:
```javascript
silenceChecker = setInterval(() => {
  analyser.getByteTimeDomainData(pcmData);
  const rms = Math.sqrt(sum / pcmData.length);   // RMS of PCM frame

  if (rms > 0.012)  → mark hadSpeech = true, reset silenceStart
  else if hadSpeech → track silenceStart; if > 2000 ms → mediaRecorder.stop()
}, 100);
```

### No-Speech Guard
If the user taps the mic but never speaks, a 4-second `setTimeout` auto-cancels:
```javascript
noSpeechTimer = setTimeout(() => {
  if (!hadSpeech && mediaRecorder.state === "recording") {
    audioChunks = [];          // discard — onstop skips sending
    mediaRecorder.stop();
    appendStatusMessage("No speech detected — tap the mic and speak clearly.", true);
  }
}, 4000);
```
Once speech is detected, the timer is cleared with `clearTimeout(noSpeechTimer)`.

### Cleanup Function
A shared `cleanup()` centralises resource teardown on all exit paths (auto-stop, manual stop, permission error):
```javascript
const cleanup = () => {
  clearInterval(silenceChecker);
  clearTimeout(noSpeechTimer);
  audioCtx.close().catch(() => {});
  stream.getTracks().forEach((t) => t.stop());
};
```

### Dark Mode
```javascript
function setTheme(dark) {
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  elements.themeIcon.innerHTML = dark ? MOON_SVG : SUN_SVG;
  localStorage.setItem("wgpt-theme", dark ? "dark" : "light");
}

function initDarkMode() {
  const saved = localStorage.getItem("wgpt-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(saved ? saved === "dark" : prefersDark);   // respects OS preference on first visit
  elements.themeToggle.addEventListener("click", () => setTheme(...toggle));
}
```

**Priority:** `localStorage` saved preference > OS `prefers-color-scheme` > light fallback.

### Send Button — SVG Arrow
`setSending()` now injects an inline SVG up-arrow on the send button to match the new design system (no dependency on font glyphs).

---

## Summary Table

| Area | Change | Impact |
|---|---|---|
| Color palette | Indigo + amber, full dark tokens | Visual |
| Typography | Inter (Google Fonts) | Visual |
| Location button | Moved topbar → pill style | Layout + UX |
| Mic button | `◉` → SVG mic + ripple rings | Visual + UX |
| Voice auto-stop | RMS silence detection (2 s) | UX |
| No-speech guard | 4 s auto-cancel | UX |
| Dark mode | `data-theme` toggle + `localStorage` | UX |
| WeatherGPT label | Removed from assistant cards | Visual |
| Loading indicator | CSS spinner instead of italic text | Visual |
| Message entrance | `fadeSlideUp` animation | Visual |
| Backend | **Untouched** | — |
| `schemas.py` | **Frozen** | — |
