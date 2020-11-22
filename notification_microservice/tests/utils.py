from notification_microservice.database import db
from datetime import datetime, timedelta, time
import random
from flask import Flask
from werkzeug.security import generate_password_hash
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
        password=pswd, dateofbirth=datetime.now(), is_active=1,
        is_admin=False, is_positive=False)
        # print(f"Adding user {user}")
        # send request to User service and get back id of created user
        users.append(requests.post(f'http://{os.environ.get("GOS_USER")}/user', json=user).json())
    return users

# def delete_random_users(app: Flask):
#     with app.app_context():
#         delete_query = User.__table__.delete().where(User.email.like('test_%'))
#         db.session.execute(delete_query)
#         db.session.commit()

counter = 1
def add_restaurants(n_places: int):
    # create restaurant through restaurant service
    global counter
    rests = []
    for i in range(n_places):
        stay_time = time(hour=1)
        restaurant = dict(name=f'test_rest_{i}', likes = 10, lat = 42.111,lon = 11.111, phone = '388493490'+str(counter),
            extra_info = '', avg_stay_time=stay_time.strftime("%H:%M:%S"))
        response = requests.post(f'http://{os.environ.get("GOS_RESTAURANT")}/restaurants/new', json=restaurant)
        rests.append(response.json()['id'])
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
    

# def random_datetime_in_range(start, end):
#     # from https://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates#answer-553448
#     if start == end:
#         return start
#     delta = end - start
#     int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
#     random_second = random.randrange(int_delta)
#     return start + timedelta(seconds=random_second)

def mark_user_as_positive(user_id: int, positive_date: datetime):
    # request User service to set one user as positive
    print(f"Marking user {user_id} as positive to COVID-19")
    resp = requests.post(f"http://{os.environ.get('GOS_USER')}/user/{user_id}/is_positive", json="True")
    resp = requests.post(f"http://{os.environ.get('GOS_USER')}/user/{user_id}/confirmed_positive_date", json=positive_date.isoformat())
    return user_id

# def visit_places(pos_id:int, positive_date: datetime, time_span: int, n_places: int, restaurant_ids, time_span_offset:int=5):
#     # return visits to places within time_span days
#     visits = []
#     risky_places = 0
#     risky_date = positive_date - timedelta(days=time_span)
#     risky_date.replace(hour=0, minute=0, second=0, microsecond=0)
#     # visit n_places unique restaurants
#     res_ids = random.sample(restaurant_ids, k=n_places)
#     # make a bunch of reservations
#     for i in range(n_places):
#         # visit a random restaurant not seen before
#         visit_date = random_datetime_in_range(positive_date-timedelta(days=time_span+time_span_offset), positive_date)
#         visit = Reservation(user_id=pos_id, 
#         restaurant_id=res_ids[i], reservation_time=visit_date, 
#         table_no=0, seats=1, entrance_time=visit_date)
#         if visit_date >= risky_date:
#             visits.append(visit)
#             risky_places += 1
#     db.session.add_all(visits)
#     db.session.commit()
#     return risky_places, [v.to_dict() for v in visits]

def add_visits_to_place(restaurant_id:int, visit_date: datetime, users_ids):
    # request Reservation service to add reservations
    visits_ids = []
    # make a bunch of reservations
    for i, uid in enumerate(users_ids):
        visit = dict(user_id=uid, restaurant_id=restaurant_id,
         reservation_time=visit_date.isoformat(), seats=4, entrance_time=visit_date)
        resp = requests.post(f'http://{os.environ.get("GOS_RESERVATION")}/reserve', json=visit)
        visits_ids.append(resp.json()['id'])
    return visits_ids
