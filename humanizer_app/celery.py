# humanizer_app/celery.py
"""
This file is the entry point for the Celery worker.
It creates the Flask application and exposes the Celery instance.
"""
from humanizer_app import create_app

# Create the Flask app instance. This is necessary for the worker
# to have access to the application context.
app = create_app()

# The Celery instance is created and attached to the app in create_app().
# We retrieve it from the app's extensions.
celery = app.extensions["celery"]
