"""
OTP Tools - Pluggable OTP sending and verification.

Supports:
- Twilio Verify (production)
- Fallback (demo) if Twilio not configured

Environment variables for Twilio Verify:
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_VERIFY_SERVICE_SID
"""
from typing import Dict, Any
import os


def is_twilio_configured() -> bool:
    return all([
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN"),
        os.getenv("TWILIO_VERIFY_SERVICE_SID"),
    ])


def send_otp_via_twilio(phone: str) -> Dict[str, Any]:
    try:
        from twilio.rest import Client
    except Exception as e:
        return {
            "success": False,
            "error": f"Twilio client not available: {e}",
        }

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID")
    client = Client(account_sid, auth_token)

    try:
        verification = client.verify.v2.services(service_sid).verifications.create(
            to=phone,
            channel="sms",
        )
        # Do not include OTP in message; Twilio sends it directly to the user.
        return {
            "success": True,
            "provider": "twilio",
            "status": verification.status,
            "message": f"✅ OTP sent to {phone}. Please enter the 6-digit code.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send OTP via Twilio: {e}",
        }


def verify_otp_via_twilio(phone: str, code: str) -> Dict[str, Any]:
    try:
        from twilio.rest import Client
    except Exception as e:
        return {
            "success": False,
            "error": f"Twilio client not available: {e}",
        }

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID")
    client = Client(account_sid, auth_token)

    try:
        check = client.verify.v2.services(service_sid).verification_checks.create(
            to=phone,
            code=code,
        )
        approved = (check.status == "approved")
        return {
            "success": True,
            "verified": approved,
            "status": check.status,
            "message": "✅ Phone Verification Successful!" if approved else "❌ Incorrect OTP. Please try again.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to verify OTP via Twilio: {e}",
        }


def send_otp(phone: str) -> Dict[str, Any]:
    if is_twilio_configured():
        return send_otp_via_twilio(phone)
    # Not configured: the workflow will use fallback demo path
    return {
        "success": False,
        "error": "Twilio not configured",
    }


def verify_otp(phone: str, code: str) -> Dict[str, Any]:
    if is_twilio_configured():
        return verify_otp_via_twilio(phone, code)
    return {
        "success": False,
        "error": "Twilio not configured",
    }
