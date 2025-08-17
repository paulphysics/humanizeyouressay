web: gunicorn run:app
worker: celery -A "humanizer_app:create_app()" worker --loglevel=info
release: flask db upgrade
