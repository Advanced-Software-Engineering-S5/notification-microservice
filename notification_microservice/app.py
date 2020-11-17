# from database import Restaurant
import connexion, logging
from database import db

db_session = None
def get_notifications(user_id):
    return 'hi'

def get_notification(user_id: int, notification_id):
    return 'hello'

logging.basicConfig(level=logging.INFO)
def create_app(dbfile='sqlite:///notification_gooutsafe.db'):
    # db_session = database.init_db('sqlite:///restaurant.db')
    app = connexion.App(__name__)
    app.add_api('swagger.yml')
    app = app.app
    # app.config['WTF_CSRF_SECRET_KEY'] = 'A SECRET KEY'
    # app.config['SECRET_KEY'] = 'ANOTHER ONE'
    app.config['SQLALCHEMY_DATABASE_URI'] = dbfile
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # celery config
    app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379'
    app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379'

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
    app.run(port=8080)