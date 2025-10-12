import os
import requests
from flask import Blueprint, request, jsonify, redirect, url_for, current_app, flash
from flask_login import current_user
from humanizer_app.extensions import db
from humanizer_app.models import User

paypal_bp = Blueprint("paypal_bp", __name__)


def get_paypal_base():
    """Return sandbox or live PayPal API base depending on environment."""
    if os.getenv("FLASK_ENV") == "production":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def get_access_token():
    """Obtain OAuth2 access token from PayPal."""
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    secret = os.getenv("PAYPAL_SECRET")
    base = get_paypal_base()
    res = requests.post(
        f"{base}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
    )
    res.raise_for_status()
    return res.json()["access_token"]


@paypal_bp.route("/paypal/create_payment")
def create_payment():
    """Create a PayPal order and redirect user to approval link."""
    amount = request.args.get("amount", type=float)
    if not amount or amount <= 0:
        return "Invalid amount", 400

    token = get_access_token()
    base = get_paypal_base()

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {"amount": {"currency_code": "USD", "value": str(amount)}}
        ],
        "application_context": {
            "return_url": url_for("paypal_bp.paypal_success", _external=True, amount=amount),
            "cancel_url": url_for("paypal_bp.paypal_cancel", _external=True),
        },
    }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(f"{base}/v2/checkout/orders", json=payload, headers=headers)
    r.raise_for_status()
    data = r.json()

    for link in data.get("links", []):
        if link.get("rel") == "approve":
            return redirect(link["href"])
    return "Unable to create PayPal payment", 400


@paypal_bp.route("/paypal/success")
def paypal_success():
    """Capture PayPal order after successful approval and credit user wallet."""
    order_id = request.args.get("token")
    amount = request.args.get("amount", type=float, default=0.0)
    if not order_id:
        return "Missing order ID", 400

    token = get_access_token()
    base = get_paypal_base()
    headers = {"Authorization": f"Bearer {token}"}

    # Capture order
    r = requests.post(f"{base}/v2/checkout/orders/{order_id}/capture", headers=headers)
    data = r.json()
    status = data.get("status")

    if status != "COMPLETED":
        flash("PayPal payment verification failed. Please contact support.", "danger")
        return redirect(url_for("main_bp.dashboard"))

    # ✅ Apply your formula: (exchange_rate - 5) × amount
    try:
        exchange_rate = float(os.getenv("USD_KES_RATE", 130))
        effective_rate = max(exchange_rate - 5, 0)
        credits_to_add = amount * effective_rate
    except Exception as e:
        current_app.logger.error(f"Exchange rate calculation failed: {e}")
        credits_to_add = 0

    # ✅ Update user wallet (credits)
    if current_user.is_authenticated:
        current_user.wallet_balance = (current_user.wallet_balance or 0) + credits_to_add
        db.session.commit()
        flash(f"Payment successful! {int(credits_to_add)} credits added to your wallet.", "success")
    else:
        flash("Payment confirmed, but user not logged in.", "warning")

    return redirect(url_for("main_bp.dashboard"))


@paypal_bp.route("/paypal/cancel")
def paypal_cancel():
    """Handle user cancellation."""
    flash("Payment cancelled.", "info")
    return redirect(url_for("main_bp.dashboard"))
