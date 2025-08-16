from celery import Celery, Task

def celery_init_app(app) -> Celery:
    """
    Factory to create and configure a Celery app instance,
    and automatically wrap tasks in the Flask application context.
    """
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    
    # Store the celery app instance on the flask app object
    app.extensions["celery"] = celery_app
    return celery_app
