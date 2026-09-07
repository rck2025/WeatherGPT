"""
End-to-End Test for Voice-to-Voice Command Center (/voice/process)
"""
import asyncio
import io
import json
import sys
from pathlib import Path
import httpx
import edge_tts

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def main():
    print("=" * 60)
    print("TESTING WEATHERGPT SEAMLESS VOICE-TO-VOICE LOOP")
    print("=" * 60)

    # 1. Synthesise test query in Hindi: "Kolkata mausam ka hal batao"
    test_phrase = "Kolkata mausam ka hal batao"
    print(f"\n[1] Generating synthetic audio for query: '{test_phrase}'...")
    communicate = edge_tts.Communicate(test_phrase, "hi-IN-SwaraNeural")
    audio_buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.extend(chunk["data"])

    print(f"    Synthetic audio generated: {len(audio_buffer)} bytes.")
    assert len(audio_buffer) > 0, "Generated audio buffer is empty!"

    # 2. Send POST /voice/process to live server
    print("\n[2] Dispatching audio blob to POST http://localhost:8000/voice/process...")
    files = {
        "file": ("test_voice.mp3", bytes(audio_buffer), "audio/mpeg")
    }
    data = {
        "language": "hi",
        "location": json.dumps({"city": "Kolkata", "state": "West Bengal", "country": "India"})
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("http://localhost:8000/voice/process", files=files, data=data)
        
        print(f"    Server response status: {response.status_code}")
        if response.status_code != 200:
            print(f"    ERROR DETAIL: {response.text}")
            sys.exit(1)

        result = response.json()
        print("\n[3] Validating ChatResponse payload:")
        print(f"    - Transcribed Query : {result.get('transcribed_query')}")
        print(f"    - Location Resolved : {result.get('location', {}).get('city')}")
        print(f"    - Weather Temp      : {result.get('weather', {}).get('current', {}).get('temperature')}°C")
        print(f"    - Audio URL         : {result.get('audio_url')}")
        print(f"    - Audio Base64 Len  : {len(result.get('audio_base64') or '')}")
        print(f"    - Bot Reply (head)  : {result.get('bot_reply', '')[:120]}...")

        # Assertions
        assert result.get("transcribed_query"), "Missing transcribed_query!"
        assert result.get("bot_reply"), "Missing bot_reply!"
        assert result.get("audio_url"), "Missing audio_url!"
        assert result.get("audio_base64", "").startswith("data:audio/mp3;base64,"), "Invalid audio_base64 prefix!"

        # 4. Verify that audio_url is accessible
        audio_url = result.get("audio_url")
        audio_res = await client.get(f"http://localhost:8000{audio_url}")
        print(f"\n[4] Validating GET http://localhost:8000{audio_url}:")
        print(f"    - Status: {audio_res.status_code}")
        print(f"    - Content-Type: {audio_res.headers.get('content-type')}")
        print(f"    - File bytes: {len(audio_res.content)}")
        assert audio_res.status_code == 200, f"Audio file fetch failed with status {audio_res.status_code}"
        assert len(audio_res.content) > 1000, "Audio content too small"

    print("\n" + "=" * 60)
    print("SUCCESS: ALL VOICE-TO-VOICE PIPELINE CHECKS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
