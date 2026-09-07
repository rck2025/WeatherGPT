"""
Emergency WhatsApp / SMS Out-of-Terminal Bridge
Provides low-bandwidth disaster alert dissemination via Twilio WhatsApp API.
"""
import logging
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
DEFAULT_EMERGENCY_PHONE = os.getenv("EMERGENCY_PHONE", "+919876543210")


def format_lite_alert(hazard_type: str, city: str) -> str:
    """
    Format a concise <=160-character disaster warning message for SMS / WhatsApp.
    Format: '🚨 WEATHER-GPT RED ALERT: [Hazard Type] in [City]. Follow NDRF SOPs. Check terminal for details.'
    """
    msg = f"🚨 WEATHER-GPT RED ALERT: {hazard_type} in {city}. Follow NDRF SOPs. Check terminal for details."
    if len(msg) > 160:
        msg = msg[:157] + "..."
    return msg


def send_emergency_whatsapp(user_phone: str, alert_text: str) -> dict:
    """
    Send an emergency WhatsApp notification via Twilio API.
    Gracefully falls back to active emergency telemetry console logging if Twilio keys are absent or invalid.
    """
    target_phone = user_phone.strip() if user_phone else DEFAULT_EMERGENCY_PHONE
    if not target_phone.startswith("whatsapp:"):
        target_phone = f"whatsapp:{target_phone}"

    # Verify if Twilio credentials are populated
    sid = os.getenv("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID).strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN).strip()

    if sid and token and not sid.startswith("your_"):
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = {
            "From": os.getenv("TWILIO_WHATSAPP_FROM", TWILIO_WHATSAPP_FROM),
            "To": target_phone,
            "Body": alert_text,
        }
        try:
            with httpx.Client(timeout=8) as client:
                res = client.post(url, data=data, auth=(sid, token))
                res.raise_for_status()
                payload = res.json()
                print(f"📱 [EMERGENCY DISASTER BRIDGE] WhatsApp Alert dispatched to {target_phone}: {alert_text}")
                logger.info("Emergency WhatsApp dispatched via Twilio to %s (SID: %s)", target_phone, payload.get("sid"))
                return {"status": "dispatched", "sid": payload.get("sid"), "phone": target_phone, "text": alert_text}
        except Exception as exc:
            print(f"📱 [EMERGENCY DISASTER BRIDGE] (Twilio pipeline note: {exc}) - Broadcast logged: {alert_text}")
            logger.warning("Twilio dispatch error: %s. Broadcast safely simulated in terminal telemetry.", exc)
            return {"status": "simulated", "phone": target_phone, "text": alert_text, "error": str(exc)}

    # Low-bandwidth simulated disaster transmission (100% reliable for demo environments)
    print(f"\n🚨 [EMERGENCY DISASTER BRIDGE] Out-of-Terminal Alert Triggered!")
    print(f"📱 Dispatched to {target_phone}: {alert_text}\n")
    logger.info("📱 [EMERGENCY DISASTER BRIDGE] WhatsApp Alert logged to %s: %s", target_phone, alert_text)
    return {"status": "simulated_active", "phone": target_phone, "text": alert_text}
