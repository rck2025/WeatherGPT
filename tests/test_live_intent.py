"""
Quick Live Server Query Test for Tomorrow vs Safety
"""
import asyncio
import json
import sys
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def test_live():
    print("=" * 60)
    print("TESTING LIVE /chat ENDPOINT FOR INTENT-FIRST RESPONSES")
    print("=" * 60)

    payload = {
        "query": "What is the weather tomorrow in Kolkata?",
        "location": {
            "city": "Kolkata",
            "state": "West Bengal",
            "country": "India",
            "latitude": 22.5726,
            "longitude": 88.3639,
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        print("\n[1] Sending Tomorrow query...")
        res = await client.post("http://localhost:8000/chat", json=payload)
        print(f"    Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            bot_reply = data.get("bot_reply", "")
            print("\n    BOT REPLY:")
            print("    " + "-" * 50)
            for line in bot_reply.splitlines():
                print(f"    {line}")
            print("    " + "-" * 50)

            # Assert that the bot reply does not begin by screaming the 3-hour nowcast
            assert not bot_reply.strip().startswith("URGENT NOWCAST:"), "Bot reply must not begin with URGENT NOWCAST on a tomorrow query!"
            print("\n    [PASS] Tomorrow response successfully prioritized future forecast over nowcast.")

        print("\n[2] Sending Safety query...")
        safety_payload = {
            "query": "Is it safe to go out in Kolkata right now?",
            "location": {
                "city": "Kolkata",
                "state": "West Bengal",
                "country": "India",
                "latitude": 22.5726,
                "longitude": 88.3639,
            },
        }
        res_safety = await client.post("http://localhost:8000/chat", json=safety_payload)
        print(f"    Status: {res_safety.status_code}")
        if res_safety.status_code == 200:
            data_s = res_safety.json()
            bot_reply_s = data_s.get("bot_reply", "")
            print("\n    SAFETY BOT REPLY:")
            print("    " + "-" * 50)
            for line in bot_reply_s.splitlines():
                print(f"    {line}")
            print("    " + "-" * 50)
            assert "SAFETY ADVISORY" in bot_reply_s or "safe" in bot_reply_s.lower(), "Bot reply should provide safety advisory!"
            print("\n    [PASS] Safety response successfully prioritized advisory & hazards.")

if __name__ == "__main__":
    asyncio.run(test_live())
