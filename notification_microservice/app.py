import connexion
import logging
from notification_microservice.database import db
import os

logging.basicConfig(level=logging.INFO)
def create_app(dbfile='sqlite:///notification_gooutsafe.db'):
    app = connexion.App(__name__)
    app.add_api('swagger.yml')
    app = app.app
    # app.config['WTF_CSRF_SECRET_KEY'] = 'A SECRET KEY'
    # app.config['SECRET_KEY'] = 'ANOTHER ONE'
    app.config['SQLALCHEMY_DATABASE_URI'] = dbfile
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # celery config
    app.config['CELERY_BROKER_URL'] = f"redis://{os.environ.get('GOS_REDIS')}/{os.environ.get('CELERY_DB_NUM')}"
    app.config['CELERY_RESULT_BACKEND'] = f"redis://{os.environ.get('GOS_REDIS')}/{os.environ.get('CELERY_DB_NUM')}"

    db.init_app(app)
    db.create_all(app=app)

    # set the WSGI application callable to allow using uWSGI:
    # uwsgi --http :8080 -w app
    return app

# @application.teardown_appcontext
# def shutdown_session(exception=None):
#     db_session.remove()


if __name__ == '__main__':
    app = create_app()
    app.run()