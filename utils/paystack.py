"""
Paystack payment integration — Nigeria's leading payment gateway.
Set PAYSTACK_SECRET_KEY env var to enable live/test payments.
Test keys from https://dashboard.paystack.com/#/settings/developer
"""

import os
import secrets
import requests
from datetime import datetime
from config import TIERS


_BASE = "https://api.paystack.co"


def _secret_key() -> str:
    return os.environ.get("PAYSTACK_SECRET_KEY", "")


def _headers() -> dict:
    return {"Authorization": f"Bearer {_secret_key()}", "Content-Type": "application/json"}


def is_configured() -> bool:
    return bool(_secret_key())


def generate_reference(user_id: int, tier: str) -> str:
    token = secrets.token_hex(8).upper()
    ts    = datetime.now().strftime("%Y%m%d%H%M")
    return f"NDPR-{tier.upper()}-{user_id}-{ts}-{token}"


def initialize_transaction(
    email: str,
    amount_ngn: int,
    reference: str,
    callback_url: str = "https://ndpr-redactor.replit.app/billing",
) -> dict:
    """
    Create a Paystack payment session.
    Returns dict with keys: authorization_url, access_code, reference (on success)
    or error (on failure).
    """
    if not is_configured():
        return {"error": "Paystack secret key not configured. Set PAYSTACK_SECRET_KEY env var."}

    payload = {
        "email":      email,
        "amount":     amount_ngn * 100,   # convert ₦ to kobo
        "reference":  reference,
        "callback_url": callback_url,
        "metadata": {
            "custom_fields": [
                {"display_name": "Product", "variable_name": "product", "value": "NDPR Redactor"},
            ]
        },
    }
    try:
        r = requests.post(f"{_BASE}/transaction/initialize", json=payload,
                          headers=_headers(), timeout=15)
        data = r.json()
        if data.get("status"):
            return data["data"]
        return {"error": data.get("message", "Unknown Paystack error")}
    except requests.RequestException as e:
        return {"error": f"Network error: {e}"}


def verify_transaction(reference: str) -> dict:
    """
    Verify a payment by reference.
    Returns dict with status, amount, customer email (on success) or error.
    """
    if not is_configured():
        return {"error": "Paystack secret key not configured."}
    try:
        r = requests.get(f"{_BASE}/transaction/verify/{reference}",
                         headers=_headers(), timeout=15)
        data = r.json()
        if data.get("status") and data["data"]["status"] == "success":
            return {
                "success":  True,
                "amount_ngn": data["data"]["amount"] // 100,
                "email":    data["data"]["customer"]["email"],
                "paid_at":  data["data"]["paid_at"],
            }
        return {"success": False, "error": data.get("message", "Payment not successful")}
    except requests.RequestException as e:
        return {"success": False, "error": f"Network error: {e}"}


def tier_amount(tier: str) -> int:
    return TIERS.get(tier, {}).get("price_ngn") or 0
