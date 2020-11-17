from database import Restaurant, db, User, Reservation
from datetime import datetime, timedelta, time
import random
from flask import Flask
from werkzeug.security import generate_password_hash
import connexion

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

def add_random_users(n_users: int, app: Flask):
    users = []
    with app.app_context():
        pswd = generate_password_hash('test') 
        for i in range(n_users):
            user = User(email=f'test_{i}@test.com', firstname=f'test_{i}', lastname=f'test_{i}', 
            password=pswd, dateofbirth=datetime.now(), is_active=1,
            is_admin=False, is_positive=False)
            # print(f"Adding user {user}")
            users.append(user)
        db.session.add_all(users)
        db.session.commit() 

def delete_random_users(app: Flask):
    with app.app_context():
        delete_query = User.__table__.delete().where(User.email.like('test_%'))
        db.session.execute(delete_query)
        db.session.commit()

counter = 1
def add_random_restaurants(n_places: int, app: Flask):
    global counter
    with app.app_context():
        rests = []
        for i in range(n_places):
            stay_time = time(hour=1)
            res = Restaurant(name=f'test_rest_{i}', likes = 10, lat = 42.111,lon = 11.111, phone = '343493490'+str(counter),
             extra_info = '', avg_stay_time=stay_time)
            rests.append(res)
            counter += 1
        db.session.add_all(rests)
        db.session.commit()
    

def random_datetime_in_range(start, end):
    # from https://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates#answer-553448
    if start == end:
        return start
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)

def mark_random_guy_as_positive(app: Flask, positive_date: datetime):
    with app.app_context():
        rand_row = random.randrange(2, db.session.query(User).count()) 
        positive_guy = db.session.query(User)[rand_row]
        print(f"Marking user {positive_guy} as positive to COVID-19 (user_id={positive_guy.id})")
        positive_guy.is_positive = True
        positive_guy.confirmed_positive_date = positive_date
        db.session.commit()
        return positive_guy.to_dict()

def visit_random_places(app: Flask, pos_id:int, positive_date: datetime, time_span: int, n_places: int, restaurant_ids, time_span_offset:int=5):
    # return visits to places within time_span days
    visits = []
    risky_places = 0
    with app.app_context():
        risky_date = positive_date - timedelta(days=time_span)
        risky_date.replace(hour=0, minute=0, second=0, microsecond=0)
        # visit n_places unique restaurants
        res_ids = random.sample(restaurant_ids, k=n_places)
        # make a bunch of reservations
        for i in range(n_places):
            # visit a random restaurant not seen before
            visit_date = random_datetime_in_range(positive_date-timedelta(days=time_span+time_span_offset), positive_date)
            visit = Reservation(user_id=pos_id, 
            restaurant_id=res_ids[i], reservation_time=visit_date, 
            table_no=0, seats=1, entrance_time=visit_date)
            if visit_date >= risky_date:
                visits.append(visit)
                risky_places += 1
        db.session.add_all(visits)
        db.session.commit()
        return risky_places, [v.to_dict() for v in visits]

def add_random_visits_to_place(app: Flask, restaurant_id:int, start_date: datetime, end_date: datetime, pos_date:datetime, n_visits:int, users_ids=None):
    visits = []
    risky_visits = 0
    with app.app_context():
        # make a bunch of reservations
        for i in range(n_visits):
            # use provided user id if given, otherwise generate random
            rand_user = random.randint(1000, 2000) if users_ids is None else users_ids[i]
            visit_date = random_datetime_in_range(start_date, end_date)
            # compute 'danger period' in which user might have been in contact with positive dude
            stay_time = Restaurant.query.filter_by(id=restaurant_id).first().avg_stay_time
            staying_interval = timedelta(hours=stay_time.hour, minutes=stay_time.minute, seconds=stay_time.second)
            if visit_date <= (pos_date + staying_interval) and visit_date >= (pos_date - staying_interval) :
                print("RISKY VISIT:", visit_date, pos_date, rand_user, restaurant_id)
                risky_visits += 1
            visit = Reservation(user_id=rand_user, 
            restaurant_id=restaurant_id, reservation_time=visit_date, 
            table_no=0, seats=1, entrance_time=visit_date)
            visits.append(visit)
        db.session.add_all(visits)
        db.session.commit()
        return risky_visits
