from datetime import datetime, timedelta
from app import create_app
from celery import Celery

BACKEND = BROKER = 'redis://localhost:6379'
def make_celery(app):
    # create celery object from single flask app configuration
    celery = Celery(__name__, backend=app.config['CELERY_RESULT_BACKEND'], 
    broker=app.config['CELERY_BROKER_URL'], 
    include=['notifications_tasks']) # include list of modules to import when worker starts

    celery.conf.update(app.config)
    # subclass celery task so that each task execution is wrapped in an app context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery = make_celery(create_app())


# _APP = None


# @celery.task
# def do_task():
#     global _APP
#     # lazy init
#     if _APP is None:
#         from monolith.app import create_app
#         app = create_app()
#         db.init_app(app)
#     else:
#         app = _APP

#     return []

