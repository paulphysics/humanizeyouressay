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
from .celery import celery_init_app

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
        "gemini-2.5-pro": {
            # --- FINAL CORRECTED API ID ---
            "api_id": "gemini-2.5-pro",
            # ------------------------------
            "price_per_word": 0.015,
            "label": "Gemini 2.5 Pro",
            "disabled": True
        },
        "gpt-5": {
            "api_id": "gpt-5-2025-08-07",
            "price_per_word": 0.012,
            "label": "ChatGPT 5"
        },
        "gpt-4o": {
            "api_id": "gpt-4o-2024-08-06",
            "price_per_word": 0.0085,
            "label": "ChatGPT 4o"
        }
    }
    DEFAULT_MODEL_KEY = "gpt-5"
    app.config["MODELS"] = MODELS
    app.config["DEFAULT_MODEL_KEY"] = DEFAULT_MODEL_KEY
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

    # --- Celery Configuration (with SSL fix) ---
    redis_url = os.getenv("REDIS_URL")
    if redis_url and redis_url.startswith("rediss://"):
        redis_url += "?ssl_cert_reqs=CERT_NONE"
    
    app.config.from_mapping(
        CELERY=dict(
            broker_url=redis_url,
            result_backend=redis_url,
            task_ignore_result=True,
            broker_connection_retry_on_startup=True
        ),
    )
    # ----------------------------------------

    # --- Upload Limits ---
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

    # --- Admin Theme ---
    app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

    # --- Initialize Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    celery_init_app(app)

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
