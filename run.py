# FILE: run.py
"""
Application entry point.
"""
from humanizer_app import create_app, db

# The application factory instance
app = create_app()

# NOTE: Firebase initialization has been moved to __init__.py
# to ensure it runs correctly on Heroku.

if __name__ == '__main__':
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()
    # This is for local development
    app.run(host="0.0.0.0", port=5000, debug=True)
