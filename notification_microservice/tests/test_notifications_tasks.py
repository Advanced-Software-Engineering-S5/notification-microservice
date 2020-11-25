import unittest
from notification_microservice.database import Notification, db
import random
from datetime import datetime, timedelta
from notification_microservice.classes.notifications_tasks import check_visited_places, create_notifications, contact_tracing
from notification_microservice.tests.utils import *
from celery.contrib.testing.worker import start_worker
from notification_microservice.background import make_celery

app = create_app_for_test()
INCUBATION_PERIOD_COVID= 14
RESTAURANT_TEST_IDS = list(range(10, 100))
N_USERS = 3

class NotificationsTasks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # start celery worker with test app context and in-memory context 
        celery_app = make_celery(app)
        cls.celery_worker = start_worker(celery_app, perform_ping_check=False)
        # spawn celery worker
        cls.celery_worker.__enter__()
        
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # kill celery worker when tests are done
        cls.celery_worker.__exit__(None, None, None)

    def setUp(self):
        db.create_all(app=app)
        # executed before executing each test
        self.now = datetime.now()
        # create some user
        self.uids = add_users_to_user_service(N_USERS)
        # create a resturant
        self.rest_id = add_restaurants(1)[0]
        print(self.uids, self.rest_id)

        self.visits_ids = []
        # LHA marks a User as positive (admin excluded)
        # self.positive_guy = mark_user_as_positive(self.uids[0], self.now)
        # have all users visit the same place at the same time
        self.visits_ids = add_visits_to_place(self.rest_id, self.now, self.uids)
        print("Visits ids", self.visits_ids)

    def tearDown(self):
        db.drop_all(app=app)
        # delete users created in User service
        for id in self.uids:
            resp = requests.delete(f"http://{os.environ.get('GOS_USER')}/users/{id}")
        # restaurant too
        resp = requests.delete(f"http://{os.environ.get('GOS_RESTAURANT')}/restaurants/{self.rest_id}")
        # as well as reservations 
        for id in self.visits_ids:
            resp = requests.delete(f"http://{os.environ.get('GOS_RESERVATION')}/customer_reservation/{id}")

    
    def test_contact_tracing(self):
        try:
            # check if positive guy visited any restaurant in the last `INCUBATION_PERIOD_COVID` days
            reservations = check_visited_places(self.uids[0], INCUBATION_PERIOD_COVID)
            print("CHECK VISITED PLACES OUT", reservations)
            # notify customers that have been to the same restaurants at the same time as the pos guy
            notified_users = contact_tracing(reservations, self.uids[0])
            print("Notified users", notified_users)

            self.assertEqual(len(notified_users), len(self.uids)-1)
        except Exception as e:
            self.fail("Exception raised during test exec")


    # here we need to have celery workers processes up and running
    def test_user_visited_places_async(self):
        try:
            with app.app_context():
                # check if positive guy visited any restaurant in the last `INCUBATION_PERIOD_COVID` days
                reservations = check_visited_places.delay(self.uids[0], INCUBATION_PERIOD_COVID).get()
            self.assertEqual(len(reservations), 1)
        except Exception as e:
            self.fail("Exception raised during test exec")

    def test_contact_tracing_async(self):
        try:
            # check if positive guy visited any restaurant in the last `INCUBATION_PERIOD_COVID` days
            reservations = check_visited_places.delay(self.uids[0], INCUBATION_PERIOD_COVID).get()
            # notify customers that have been to the same restaurants at the same time as the pos guy
            notified_users = contact_tracing.delay(reservations, self.uids[0]).get()
            print("Notified users", notified_users)

            self.assertEqual(len(notified_users), len(self.uids)-1)
        except Exception as e:
            self.fail("Exception raised during test exec")


    def test_user_notification_async(self):
        try:
            with app.app_context():
                # run async tasks: check visited places -> check customers in danger -> write notifications
                exec_chain = (check_visited_places.s(self.uids[0], INCUBATION_PERIOD_COVID) |
                contact_tracing.s(self.uids[0]) | create_notifications.s(self.uids[0]))()
                notifs = exec_chain.get()
                db_notifications = [n.to_dict() for n in Notification.query.filter_by(user_notification=True).all()]
                print("User Notifications in db:", db_notifications)
                # make sure every user got their notification
                for user_id in self.uids[1:]:
                    user_not = Notification.query.filter_by(user_id=user_id, user_notification=True).all()
                    print(f"[{user_id}] USER NOTIFICATION:", user_not[0].to_dict())
                    self.assertEqual(len(user_not), 1)
                    
                # check that every user had their notifications generated
                self.assertEqual(len(db_notifications), len(self.uids)-1)
        except Exception as e:
            self.fail("Exception raised during test exec")

    