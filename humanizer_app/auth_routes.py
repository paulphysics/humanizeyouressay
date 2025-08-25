from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template
from firebase_admin import auth
from functools import wraps
from .extensions import db
from .models import User, Wallet, Transaction # Import Transaction
from .payment_service import WORDS_PER_UNIT, PRICE_PER_UNIT
import os
import uuid # Import uuid

# Create a Blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)

# Decorator to protect routes that require authentication
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login')) # Redirect to the login page
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/auth', methods=['POST'])
def authorize():
    """
    Receives an ID token from the client, verifies it, creates/updates a local user
    and wallet, captures the user's name, and creates a server-side session.
    Also handles referral codes for new users.
    """
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return "Unauthorized", 401

    id_token = token.split('Bearer ')[1]
    
    # --- ADDITION: Get referral code from the request body ---
    # The frontend now sends this in the JSON payload
    data = request.get_json()
    referral_code = data.get('referral_code') if data else None

    try:
        decoded_token = auth.verify_id_token(id_token, check_revoked=True)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name')

        user = User.query.get(uid)

        if not user:
            if User.query.filter_by(email=email).first():
                return "An account with a different sign-in method already exists for this email.", 409

            new_user = User(id=uid, email=email, name=name)
            
            # --- REFERRAL LOGIC START ---
            # 1. Generate a unique referral code for the new user
            new_user.referral_code = f"REF-{str(uuid.uuid4())[:8].upper()}"

            # 2. Check if a referral code was provided and apply it
            if referral_code:
                referrer = User.query.filter_by(referral_code=referral_code).first()
                if referrer:
                    new_user.referred_by = referrer.id
                    # Optional: Give the referrer a one-time bonus for a successful referral
                    if referrer.wallet:
                        referrer.wallet.balance += 5.0  # Example: 5 credit bonus
                        db.session.add(Transaction(wallet_id=referrer.wallet.id, amount=5.0, transaction_type='referral_signup_bonus', description=f'Bonus for referring {email}'))
            # --- REFERRAL LOGIC END ---

            new_wallet = Wallet(user=new_user, balance=0.0)
            db.session.add(new_user)
            db.session.add(new_wallet)
            db.session.commit()
            user = new_user
        else:
            if name and user.name != name:
                user.name = name
                db.session.commit()

        session['user'] = {
            'uid': user.id,
            'email': user.email,
            'name': user.name
        }
        session.permanent = True
        
        # --- MODIFICATION START ---
        # Return a JSON object with the user's admin status
        return jsonify({"message": "Login successful", "is_admin": user.is_admin}), 200
        # --- MODIFICATION END ---

    except Exception as e:
        print(f"An error occurred during authorization: {e}")
        return f"An error occurred: {e}", 500

# --- Public Routes for Auth Pages ---

@auth_bp.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('main.home'))
    
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
    }
    return render_template('login.html', firebase_config=firebase_config)

@auth_bp.route('/signup')
def signup():
    if 'user' in session:
        return redirect(url_for('main.home'))
        
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
    }
    return render_template('signup.html', firebase_config=firebase_config)


@auth_bp.route('/logout')
def logout():
    session.pop('user', None) # Clear the user session
    return redirect(url_for('auth.login'))
