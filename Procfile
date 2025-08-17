release: flask db upgrade
web: gunicorn run:app
worker: celery -A run.celery worker --loglevel=info --concurrency=1 -P gevent --max-tasks-per-child 10
