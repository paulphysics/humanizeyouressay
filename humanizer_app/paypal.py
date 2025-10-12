# humanizer_service/paypal.py
from flask import Blueprint, request, redirect, url_for, render_template
import paypalrestsdk

paypal_bp = Blueprint('paypal', __name__)

# --- PAYPAL CONFIG ---
paypalrestsdk.configure({
    "mode": "sandbox",  # change to "live" when going live
    "client_id": "YOUR_PAYPAL_CLIENT_ID",
    "client_secret": "YOUR_PAYPAL_CLIENT_SECRET"
})


# --- CREATE PAYMENT ---
@paypal_bp.route('/pay_paypal', methods=['POST'])
def pay_paypal():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": url_for('paypal.paypal_execute', _external=True),
            "cancel_url": url_for('paypal.paypal_cancel', _external=True)
        },
        "transactions": [{
            "amount": {"total": "5.00", "currency": "USD"},
            "description": "Humanize Your Essay plan payment"
        }]
    })

    if payment.create():
        return redirect(next(link.href for link in payment.links if link.method == "REDIRECT"))
    return "Error creating PayPal payment", 400


# --- VERIFY PAYMENT ---
@paypal_bp.route('/paypal_execute')
def paypal_execute():
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        # ✅ Verified — integrate with your database here
        return render_template('success.html', payment=payment)
    return "Payment verification failed", 400


# --- CANCEL ---
@paypal_bp.route('/paypal_cancel')
def paypal_cancel():
    return render_template('cancel.html')
