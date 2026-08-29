# Frontend <-> Backend Communication Plan

This document outlines the data flow between the frontend application and the backend API, specifically focusing on the core `/chat` endpoint. It defines exactly what data the frontend should send, what it receives in return, and how that information should be displayed to the user.

---

## 1. Inputs (Frontend to Backend)

The frontend communicates with the backend via a single POST request to the `/chat` endpoint. The data sent matches the `ChatRequest` schema.

### Data Structure (`ChatRequest`)
```json
{
  "query": "What is the weather today?",
  "language": "hi",
  "channel": "web",
  "location": {
    "latitude": 22.48,
    "longitude": 88.39,
    "city": "Kolkata",
    "raw_text": "Salt Lake Sector 5" 
  }
}
```

### Breakdown of Inputs
* **`query` (String, Required):** The actual question or statement from the user. This can come from typed text in the input box, or from speech-to-text transcription.
* **`language` (String):** The BCP-47 or ISO code (e.g., `"en"`, `"hi"`, `"bn"`) representing the user's selected language. This tells the backend what language to translate the bot's reply into.
* **`channel` (String):** Indicates the mode of communication. It should be `"web"` for standard text queries, or `"voice"` if the user used the microphone. If `"voice"`, the backend will generate and return an audio file URL.
* **`location` (Object, Optional):** The user's location. This is crucial for accurate weather data.
  * *GPS Mode:* Pass `latitude` and `longitude`.
  * *Manual Mode:* Pass `raw_text` (e.g., a city name, address, or PIN code).

---

## 2. Outputs (Backend to Frontend)

The backend processes the query, translates it, fetches weather and RAG data, and responds with a `ChatResponse` object.

### Data Structure (`ChatResponse`)
```json
{
  "bot_reply": "आज का मौसम कैसा है...\n\n---\n\n**English Version:**\n\nHere is the weather today...",
  "location": {
    "latitude": 22.48,
    "longitude": 88.39,
    "city": "Kolkata",
    "country": "India"
  },
  "weather": {
    "current": {
      "temperature": 32.5,
      "feels_like": 36.2,
      "humidity": 80.0
    },
    "hourly": [...],
    "daily": [...]
  },
  "alerts": [
    {
      "title": "Heavy Rain Warning",
      "severity": "High",
      "source": "IMD"
    }
  ],
  "sources": [
    {
      "content": "IMD Bulletin snippet...",
      "source": "imd_bulletin_today.pdf"
    }
  ],
  "audio_url": "/voice/audio/response_1234.mp3" 
}
```

---

## 3. What to Display in the UI

Based on the outputs above, the frontend should dynamically render the following elements:

### A. The Chat Stream
* **User Bubble:** Display the exact string sent in `request.query`.
* **Assistant Bubble:** Display `response.bot_reply` rendered as Markdown. If the user selected a regional language, this will now contain both the native text and the English fallback.
* **Audio Playback:** If `response.audio_url` is present (because `channel === "voice"`), attach an `<audio controls autoplay>` player directly below the assistant's text bubble.

### B. Context & Metadata Pills
To build trust and provide quick scannable context, display small UI "pills" or tags below the assistant's text bubble:
* **Location context:** Show `response.location.city` (e.g., "📍 Kolkata").
* **Current Temperature:** Show `response.weather.current.temperature` (e.g., "🌡️ 32.5°C now").
* **Alerts:** Iterate through `response.alerts`. If any exist, display them in red/orange warning pills (e.g., "⚠️ High: Heavy Rain Warning").
* **RAG Sources:** Iterate through `response.sources` and display the document names so the user knows where the AI got its information (e.g., "📄 imd_bulletin_today.pdf").

### C. Persistent UI Elements
* **Location Panel/Status:** Keep a visible indicator at the top or bottom of the screen showing whether the app is currently using "GPS Mode" or "Manual Location Mode" so the user knows what location context is being sent.
* **Language Toggle:** A persistent dropdown allowing the user to switch languages on the fly.

> [!TIP]
> The current `app.js` implementation already handles the display of these elements beautifully using the `addMetaPill` function and markdown rendering!
