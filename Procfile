web: gunicorn run:app
worker: celery -A celery_worker.celery_app worker --loglevel=info
release: flask db upgrade
