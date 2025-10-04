import os
import uuid
import re
from functools import wraps
from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from firebase_admin import auth
from .extensions import db
from .models import User, Wallet


auth_bp = Blueprint('auth', __name__)

# Kenyan phone format validation
KENYAN_PHONE_REGEX = re.compile(r"^\+254\d{9}$")


# Decorator to protect routes that require authentication
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.auth_page'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/auth', methods=['POST'])
def authorize():
    """
    Google authentication handler.
    Verifies Firebase ID token, creates user if not exists (without phone yet), starts session.
    """
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({"error": "unauthorized"}), 401

    id_token = token.split('Bearer ')[1]

    try:
        decoded_token = auth.verify_id_token(id_token, check_revoked=True)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name')

        user = User.query.get(uid)

        if not user:
            # Check if email already exists
            if User.query.filter_by(email=email).first():
                return jsonify({"error": "email_conflict"}), 409

            # Create user with basic details (phone will be added later)
            new_user = User(
                id=uid,
                email=email,
                name=name,
                phone_number=None,  # Will be updated in /auth/complete-signup
                referral_code=f"REF-{str(uuid.uuid4())[:8].upper()}"
            )

            # Create wallet for user
            new_wallet = Wallet(user=new_user, balance=0.0)

            db.session.add(new_user)
            db.session.add(new_wallet)
            db.session.commit()
            user = new_user
        else:
            # Update name if changed
            if name and user.name != name:
                user.name = name
                db.session.commit()

        # Create session
        session['user'] = {
            'uid': user.id,
            'email': user.email,
            'name': user.name
        }
        session.permanent = True

        # If phone is missing, tell frontend to complete signup
        needs_phone = user.phone_number is None

        return jsonify({
            "message": "Login successful",
            "is_admin": user.is_admin,
            "needs_phone": needs_phone
        }), 200

    except Exception as e:
        print(f"Error during authorization: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500


@auth_bp.route('/auth/complete-signup', methods=['POST'])
def complete_signup():
    """
    Completes user signup by adding phone number and handling referral code.
    Returns JSON with error codes for frontend mapping.
    """
    if 'user' not in session:
        return jsonify({"status": "error", "error": "unauthorized"}), 401

    data = request.get_json() or {}
    phone_number = data.get('phone_number', '').strip()
    referral_code = data.get('referral_code', '').strip() if data.get('referral_code') else None

    # Validate phone presence
    if not phone_number:
        return jsonify({"status": "error", "error": "missing_phone"}), 400

    # Validate Kenyan phone format
    if not KENYAN_PHONE_REGEX.match(phone_number):
        return jsonify({"status": "error", "error": "invalid_phone"}), 400

    # Check duplicate phone
    if User.query.filter_by(phone_number=phone_number).first():
        return jsonify({"status": "error", "error": "duplicate_phone"}), 409

    # Fetch current user
    user = User.query.get(session['user']['uid'])
    if not user:
        return jsonify({"status": "error", "error": "user_not_found"}), 404

    # If phone already exists, block
    if user.phone_number:
        return jsonify({"status": "error", "error": "already_completed"}), 400

    # Save phone number
    user.phone_number = phone_number

    # Handle referral logic
    if referral_code and not user.referred_by:
        referrer = User.query.filter_by(referral_code=referral_code).first()
        if referrer:
            user.referred_by = referrer.id
            # Construct upline (limit 4 ancestors)
            upline = [referrer.id]
            if referrer.upline:
                upline.extend(referrer.upline.split(','))
            user.upline = ",".join(upline[:4])

    db.session.commit()

    return jsonify({"status": "success", "message": "Signup completed successfully."}), 200


# --- Public Auth Pages ---
@auth_bp.route('/auth/page')
def auth_page():
    """
    Renders the Firebase authentication page.
    """
    # Check if user is already authenticated
    if 'user' in session:
        return redirect(url_for('main.index'))

    # Retrieve Firebase config from environment variables
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID")
    }

    # Pass the config to the template
    return render_template('auth.html', firebase_config=firebase_config)


@auth_bp.route('/login')
def login():
    return redirect(url_for('auth.auth_page'))


@auth_bp.route('/signup')
def signup():
    return redirect(url_for('auth.auth_page'))


@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth.auth_page'))
