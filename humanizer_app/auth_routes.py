# FILE: humanizer_app/auth_routes.py

from flask import Blueprint, request, make_response, session, redirect, url_for, render_template
from firebase_admin import auth
from functools import wraps
from .extensions import db
from .models import User, Wallet
from .payment_service import WORDS_PER_UNIT, PRICE_PER_UNIT
import os

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
    """
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return "Unauthorized", 401

    id_token = token.split('Bearer ')[1]

    try:
        decoded_token = auth.verify_id_token(id_token, check_revoked=True)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name')

        # --- THIS IS THE FIX ---
        # The primary key (user.id) should never be updated.
        # This new logic finds a user by their unique Firebase ID (uid).
        # If they don't exist, it creates them. If they do, it just updates their name.
        
        user = User.query.get(uid)

        if not user:
            # User does not exist in our database, so create them.
            # We also check if a user with that email exists to provide a better error,
            # but we do not link the accounts to prevent this exact error.
            if User.query.filter_by(email=email).first():
                # A different account (e.g., from email/password) already uses this email.
                # This is a rare edge case, but it's good to handle.
                return "An account with a different sign-in method already exists for this email.", 409

            new_user = User(id=uid, email=email, name=name)
            new_wallet = Wallet(user=new_user, balance=0.0)
            db.session.add(new_user)
            db.session.add(new_wallet)
            db.session.commit()
            user = new_user
        else:
            # User already exists, just update their name if it's new or different.
            if name and user.name != name:
                user.name = name
                db.session.commit()
        # --- END OF FIX ---

        session['user'] = {
            'uid': user.id,
            'email': user.email,
            'name': user.name
        }
        session.permanent = True
        return "Login successful", 200
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
