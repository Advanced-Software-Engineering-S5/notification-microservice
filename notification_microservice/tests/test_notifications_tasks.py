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
            print(e)
            self.fail("Exception raised during test exec")

    # def test_contact_tracing_users(self):
    #     with app.app_context():
    #         positive_guy = User.query.filter_by(is_positive=True).first().to_dict()

    #         # make positive guy visit some random places
    #         n_places = random.randrange(0, 10)
    #         nrisky_places, visits = visit_random_places(app, positive_guy['id'], self.now, INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS)
    #         # have a random num of users visit the same place as the positive guy
    #         print("PLACES VISITED BY POSITIVE:", visits)
    #         nrisky_visits = 0
    #         n_visits = random.randint(0, 4)
    #         existing_users = User.query.filter_by(is_positive=False, is_admin=False).filter(User.restaurant_id == None).all()
    #         ids = [e.id for e in existing_users]
    #         for v in visits:
    #             nrisky_visits += add_random_visits_to_place(app, v['restaurant_id'],
    #              self.now-timedelta(days=INCUBATION_PERIOD_COVID), self.now, v['entrance_time'], 1, ids)
                    
    #         # check if positive guy visited any restaurant in the last `INCUBATION_PERIOD_COVID` days
    #         reservations = check_visited_places(positive_guy['id'], INCUBATION_PERIOD_COVID)
    #         # notify customers that have been to the same restaurants at the same time as the pos guy
    #         notified_users = contact_tracing_users(reservations, positive_guy['id'])
    #         print("Notified users", notified_users)

    #     self.assertEqual(len(notified_users), nrisky_visits)

    # here we need to have celery workers processes up and running
    def test_user_visited_places_async(self):
        try:
            with app.app_context():
                # check if positive guy visited any restaurant in the last `INCUBATION_PERIOD_COVID` days
                reservations = check_visited_places.delay(self.uids[0], INCUBATION_PERIOD_COVID).get()
            self.assertEqual(len(reservations), 1)
        except Exception as e:
            print(e)
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
            print(e)
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
            print(e)
            self.fail("Exception raised during test exec")

    # def test_contact_tracing_endpoint(self):
    #     try:
    #         test_client = app.test_client()
    #         # user 0 marked as positive, contact tracing background tasks must be started
    #         resp = test_client.get(f'/notifications/contact_tracing/{self.uids[0]}')
    #         self.assertEqual(resp.status_code, 200)
    #     except Exception as e:
    #         print(e)
    #         self.fail("Exception raised during test exec")
    