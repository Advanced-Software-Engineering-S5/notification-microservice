from datetime import datetime, timedelta
from monolith.app import create_app
from celery import Celery

BACKEND = BROKER = 'redis://localhost:6379'
def make_celery(app):
    # create celery object from single flask app configuration
    celery = Celery(__name__, backend=app.config['CELERY_RESULT_BACKEND'], 
    broker=app.config['CELERY_BROKER_URL'], 
    include=['monolith.classes.notifications', 
             'monolith.classes.authority_backend',
             'monolith.classes.mail',
             'monolith.background']) # include list of modules to import when worker tarts

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

