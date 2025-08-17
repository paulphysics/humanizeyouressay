release: flask db upgrade
web: gunicorn run:app
worker: celery -A humanizer_app.celery.celery worker --loglevel=info --concurrency=1 -P gevent --max-tasks-per-child 10
