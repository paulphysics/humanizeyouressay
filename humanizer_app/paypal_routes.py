# humanizer_app/paypal_routes.py
import os
import requests
from flask import Blueprint, request, jsonify, redirect, url_for, current_app

paypal_bp = Blueprint("paypal_bp", __name__)

PAYPAL_API_BASE = (
    "https://api-m.paypal.com"
    if not current_app.debug
    else "https://api-m.sandbox.paypal.com"
)

def get_access_token():
    res = requests.post(
        f"{PAYPAL_API_BASE}/v1/oauth2/token",
        auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")),
        data={"grant_type": "client_credentials"},
    )
    res.raise_for_status()
    return res.json()["access_token"]

@paypal_bp.route("/paypal/create", methods=["POST"])
def paypal_create():
    data = request.get_json()
    amount = data.get("amount")
    token = get_access_token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": "USD", "value": str(amount)}}],
        "application_context": {
            "return_url": url_for("paypal_bp.paypal_success", _external=True),
            "cancel_url": url_for("paypal_bp.paypal_cancel", _external=True),
        },
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(f"{PAYPAL_API_BASE}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@paypal_bp.route("/paypal/success")
def paypal_success():
    order_id = request.args.get("token")
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture", headers=headers)
    # ⚙️ TODO: you can optionally update DB or send confirmation email here
    return redirect(url_for("dashboard"))

@paypal_bp.route("/paypal/cancel")
def paypal_cancel():
    return redirect(url_for("dashboard"))
