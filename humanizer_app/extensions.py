# humanizer_app/extensions.py
"""
This module initializes Flask extensions to be used across the application,
preventing circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Database extension
db = SQLAlchemy()

# Database migration extension
migrate = Migrate()
