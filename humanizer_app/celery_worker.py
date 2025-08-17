# humanizer_app/celery_worker.py
"""
This file is the entry point for the Celery worker.
It creates the Flask application and exposes the Celery instance.
"""
from humanizer_app import create_app

# Create the Flask app instance so the worker has the app context.
app = create_app()

# Retrieve the Celery instance from the app's extensions.
celery = app.extensions["celery"]

