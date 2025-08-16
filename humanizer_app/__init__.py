# FILE: humanizer_app/__init__.py
"""
Initializes the Flask application and its extensions.
This file turns the 'humanizer_app' directory into a Python package.
"""

import os
import json
import dotenv
import firebase_admin
from flask import Flask
from firebase_admin import credentials
from .extensions import db, migrate
from datetime import datetime, timedelta


# Initialize Firebase Admin SDK (before any other Firebase operations)
if not firebase_admin._apps:
    firebase_auth_json_str = os.getenv("FIREBASE_AUTH_JSON")
    if firebase_auth_json_str:
        firebase_auth_json = json.loads(firebase_auth_json_str)
        cred = credentials.Certificate(firebase_auth_json)
    else:
        cred = credentials.Certificate("firebase-auth.json")
    firebase_admin.initialize_app(cred)


def create_app():
    """
    Application factory function to create and configure the Flask app.
    """
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static'
    )

    # --- Load environment variables ---
    dotenv.load_dotenv()

    # --- Model configuration ---
    MODELS = {
        "gpt-5": {
            "api_id": "gpt-5-2025-08-07",  # exact GPT-5 snapshot confirmed to work
            "price_per_word": 0.012,
            "label": "ChatGPT 5"
        },
        "gpt-4o": {
            "api_id": "gpt-4o-2024-08-06",  # current GPT-4 Omni snapshot
            "price_per_word": 0.0085,
            "label": "ChatGPT 4o"
        }
    }
    DEFAULT_MODEL_KEY = "gpt-5"

    app.config["MODELS"] = MODELS
    app.config["DEFAULT_MODEL_KEY"] = DEFAULT_MODEL_KEY
    # Optional environment override
    app.config['DEFAULT_MODEL'] = os.environ.get('DEFAULT_MODEL', DEFAULT_MODEL_KEY)

    # --- Flask Security Config ---
    app.config['SECRET_KEY'] = os.getenv(
        "FLASK_SECRET_KEY",
        "a-very-secure-secret-key-that-you-should-change"
    )
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=5)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # --- Database Config ---
    database_url = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- Upload Limits ---
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

    # --- Admin Theme ---
    app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

    # --- Initialize Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}

    # --- Initialize Admin Panel ---
    from .admin import init_admin
    init_admin(app, db)

    # --- Register Blueprints ---
    from .routes import main_bp
    from .auth_routes import auth_bp
    from .admin_dashboard_routes import admin_dashboard_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_dashboard_bp)

    return app
