from notification_microservice.database import db
from datetime import datetime, timedelta, time
import random
import connexion
import requests, os

user_data = {'email':'prova@prova.com', 
        'firstname':'Mario', 
        'lastname':'Rossi', 
        'dateofbirth': datetime(1960, 12, 3)}

clear_password = 'pass'

restaurant_data = {'name': 'Mensa martiri', 
                    'lat': '4.12345',
                    'lon': '5.67890',
                    'phone': '3333333333',
                    'extra_info': 'Rigatoni dorati h24, cucina povera'}

def create_app_for_test():
    # creates app using in-memory sqlite db for testing purposes
    app = connexion.App(__name__)
    app.add_api('../swagger.yml')
    app = app.app
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_SECRET_KEY'] = 'A SECRET KEY'
    app.config['SECRET_KEY'] = 'ANOTHER ONE'

    # celery config
    app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379'
    app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379'

    db.init_app(app)
    db.create_all(app=app)

    # set the WSGI application callable to allow using uWSGI:
    # uwsgi --http :8080 -w app
    return app

def add_users_to_user_service(n_users: int):
    users = []
    # pswd = generate_password_hash('test') pswd should be unsalted 
    pswd = 'test'
    for i in range(n_users):
        user = dict(email=f'test_{i}@test.com', firstname=f'test_{i}', lastname=f'test_{i}', 
        password=pswd, dateofbirth=datetime.now().isoformat())
        # print(f"Adding user {user}")
        # send request to User service and get back id of created user
        users.append(requests.post(f'http://{os.environ.get("GOS_USER")}/user', json=user).json())
    return users

counter = 1
def add_restaurants(n_places: int):
    # create restaurant through restaurant service
    global counter
    rests = []
    for i in range(n_places):
        stay_time = time(hour=1)
        restaurant = dict(name=f'test_rest_{i}', lat = 42.111,lon = 11.111, phone = '382293490'+str(counter),
            extra_info = '', avg_stay_time=stay_time.strftime("%H:%M:%S"))
        response = requests.post(f'http://{os.environ.get("GOS_RESTAURANT")}/restaurants/new', json=restaurant)
        rests.append(response.json())
        # add tables to this restaurant
        body = {
            "phone": restaurant['phone'],
            "tables": [
                {
                "restaurant_id": rests[-1],
                "seats": 4,
                "table_id": i
                } for i in range (4)]
            }
        response = requests.put(f'http://{os.environ.get("GOS_RESTAURANT")}/restaurants/{rests[-1]}', json=body)
        counter += 1
    return rests
    

def mark_user_as_positive(user_id: int, positive_date: str):
    # request User service to set one user as positive
    print(f"Marking user {user_id} as positive to COVID-19")
    resp = requests.post(f"http://{os.environ.get('GOS_USER')}/user/{user_id}/is_positive", json="true")
    resp = requests.post(f"http://{os.environ.get('GOS_USER')}/user/{user_id}/confirmed_positive_date", json=positive_date.isoformat())
    return user_id

def add_visits_to_place(restaurant_id:int, visit_date: datetime, users_ids):
    # request Reservation service to add reservations
    visits_ids = []
    # make a bunch of reservations
    for i, uid in enumerate(users_ids):
        visit = dict(user_id=int(uid), restaurant_id=int(restaurant_id),
         reservation_time=visit_date.isoformat(), seats=4)
        resp = requests.post(f'http://{os.environ.get("GOS_RESERVATION")}/reserve', json=visit)
        # print("MARIO:", resp.json())
        id_ = resp.json()['id']
        visits_ids.append(id_)
        # set entrance time
        body = {"status": 3, "time": visit_date.isoformat()}
        resp = requests.put(f'http://{os.environ.get("GOS_RESERVATION")}/reservation/{id_}/status', json=body)

    return visits_ids
