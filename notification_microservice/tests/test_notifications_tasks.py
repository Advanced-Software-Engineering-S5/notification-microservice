import unittest
from notification_microservice.database import Notification, Reservation, Restaurant, db, User
import random
from datetime import datetime, timedelta
from notification_microservice.classes.notifications_tasks import check_visited_places, create_notifications, contact_tracing, contact_tracing_users
# from monolith.classes.notification_retrieval import fetch_operator_notifications, fetch_user_notifications, getAndSetNotification, fetch_notifications
from notification_microservice.tests.utils import *
from celery.contrib.testing.worker import start_worker
from notification_microservice.background import make_celery

app = create_app_for_test()
INCUBATION_PERIOD_COVID= 14
RESTAURANT_TEST_IDS = list(range(10, 100))

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
        add_random_users(10*10, app)
        add_random_restaurants(10*10, app)
        # LHA marks a User as positive (admin excluded)
        self.positive_guy = mark_random_guy_as_positive(app, self.now)

    def tearDown(self):
        db.drop_all(app=app)
        # with app.app_context():
        #     # executed after each test, regardless of outcome
        #     delete_random_users(app)
        #     # delete all reservations
        #     db.session.query(Reservation).delete()
        #     db.session.query(Notification).delete()
        #     db.session.query(Restaurant).delete()
        #     db.session.commit()
        

    def test_lha_positive_marking(self):
        with app.app_context():
            poor_guy = User.query.filter_by(is_positive=True).first()
        self.assertEqual(poor_guy.id, self.positive_guy['id'])
        self.assertEqual(poor_guy.confirmed_positive_date, self.now.date())
        self.assertNotEqual(poor_guy.id, 1)

    # uses original db 
    # def test_user_visited_places_sync(self):
    #     with app.app_context():
    #         positive_guy = User.query.get(self.positive_guy['id']).to_dict()

    #         # make it so that user visited a random number of places
    #         n_places = random.randrange(0, 10)
    #         nrisky_places, visits = visit_random_places(app, positive_guy['id'], self.now, INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS)
    #         # get restaurants visited by positive user in the last `INCUBATION_PERIOD_COVID` days
    #         reservations = check_visited_places(positive_guy['id'], INCUBATION_PERIOD_COVID)
    #     # check every positive user visit was correctly retrieved
    #     self.assertEqual(len(reservations), nrisky_places)
    #     self.assertDictEqual({v['id']:v for v in visits}, {r['id']: r for r in reservations})
    
    def test_contact_tracing(self):
        with app.app_context():
            positive_guy = User.query.filter_by(is_positive=True).first().to_dict()

            # make positive guy visit some random places
            n_places = random.randrange(0, 10)
            nrisky_places, visits = visit_random_places(app, positive_guy['id'], self.now, INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS)
            # have a random num of users visit the same place as the positive guy
            print("PLACES VISITED BY POSITIVE:", visits)
            nrisky_visits = 0
            n_visits = random.randint(0, 4)
            for v in visits:
                nrisky_visits += add_random_visits_to_place(app, v['restaurant_id'],
                 self.now-timedelta(days=INCUBATION_PERIOD_COVID), self.now, v['entrance_time'], n_visits)
                    
            # check if positive guy visited any restaurant in the last `INCUBATION_PERIOD_COVID` days
            reservations = check_visited_places(positive_guy['id'], INCUBATION_PERIOD_COVID)
            # notify customers that have been to the same restaurants at the same time as the pos guy
            notified_users = contact_tracing(reservations, positive_guy['id'])
            print("Notified users", notified_users)

        self.assertEqual(len(notified_users), nrisky_visits)

    def test_contact_tracing_users(self):
        with app.app_context():
            positive_guy = User.query.filter_by(is_positive=True).first().to_dict()

            # make positive guy visit some random places
            n_places = random.randrange(0, 10)
            nrisky_places, visits = visit_random_places(app, positive_guy['id'], self.now, INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS)
            # have a random num of users visit the same place as the positive guy
            print("PLACES VISITED BY POSITIVE:", visits)
            nrisky_visits = 0
            n_visits = random.randint(0, 4)
            existing_users = User.query.filter_by(is_positive=False, is_admin=False).filter(User.restaurant_id == None).all()
            ids = [e.id for e in existing_users]
            for v in visits:
                nrisky_visits += add_random_visits_to_place(app, v['restaurant_id'],
                 self.now-timedelta(days=INCUBATION_PERIOD_COVID), self.now, v['entrance_time'], 1, ids)
                    
            # check if positive guy visited any restaurant in the last `INCUBATION_PERIOD_COVID` days
            reservations = check_visited_places(positive_guy['id'], INCUBATION_PERIOD_COVID)
            # notify customers that have been to the same restaurants at the same time as the pos guy
            notified_users = contact_tracing_users(reservations, positive_guy['id'])
            print("Notified users", notified_users)

        self.assertEqual(len(notified_users), nrisky_visits)

    # here we need to have celery workers processes up and running
    def test_user_visited_places_async(self):
        with app.app_context():
            positive_guy = User.query.filter_by(is_positive=True).first().to_dict()
            
            # make it so that user visited a random number of places
            n_places = random.randrange(0, 10)
            nrisky_places, visits = visit_random_places(app, positive_guy['id'], self.now, INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS)
            # get restaurants visited by positive user in the last `INCUBATION_PERIOD_COVID` days
            # this forces a wait
            reservations = check_visited_places.delay(positive_guy['id'], INCUBATION_PERIOD_COVID).get()
            # print(reservations)

         # check every positive user visit was correctly retrieved
        self.assertEqual(len(reservations), nrisky_places)
        # json conversion happened
        # self.assertDictEqual({v['id']:v for v in visits}, {r['id']: r for r in reservations})

    def test_contact_tracing_async(self):
        with app.app_context():
            positive_guy = User.query.filter_by(is_positive=True).first().to_dict()

            # make positive guy visit some random places
            n_places = random.randrange(0, 10)
            nrisky_places, visits = visit_random_places(app, positive_guy['id'], self.now, INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS)
            # have a random num of users visit the same place as the positive guy
            print("PLACES VISITED BY POSITIVE:", visits)
            nrisky_visits = 0
            n_visits = random.randint(0, 4)
            for v in visits:
                nrisky_visits += add_random_visits_to_place(app, v['restaurant_id'],
                 self.now-timedelta(days=INCUBATION_PERIOD_COVID), self.now, v['entrance_time'], n_visits)
                    
            # run async task enforcing chain execution using signatures
            pos_id = positive_guy['id']
            exec_chain = (check_visited_places.s(pos_id, INCUBATION_PERIOD_COVID) | contact_tracing.s(pos_id))()
            
            to_be_notified_users = exec_chain.get()
            print("Notified users", to_be_notified_users)

        self.assertEqual(len(to_be_notified_users), nrisky_visits)

    # def test_operator_notifications(self):
    #     with app.app_context():
    #         positive_guy = User.query.filter_by(is_positive=True).first().to_dict()

    #         # generate positive user visits to random restaurants in last 14 days
    #         n_places = random.randrange(1, 10)
    #         nrisky_places, risky_visits = visit_random_places(app, positive_guy['id'], self.now,\
    #              INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS,time_span_offset=0)
    #         print(f"User {positive_guy['id']} visited {nrisky_places} restaurants")
    #         # generate other users visits to same restaurants in same days
    #         visits_per_rest = {}
    #         n_visits = random.randint(1, 3)
    #         for visit in risky_visits:
    #             rid = visit['restaurant_id']
    #             et = visit['entrance_time']
    #             visits_per_rest[rid] = add_random_visits_to_place(app, rid, et, et, et, n_visits)
    #             print(f"Some other {visits_per_rest[rid]} users visited restaurant {rid}")
    #         # execute pipeline async to generate notifications
    #         # run async tasks: check visited places -> check customers in danger -> write notifications
    #         pos_id = positive_guy['id']
    #         exec_chain = (check_visited_places.s(pos_id, INCUBATION_PERIOD_COVID) |
    #          contact_tracing.s(pos_id) | create_notifications.s(pos_id))()
            
    #         notifs = exec_chain.get()
    #         db_notifications = [n.to_dict() for n in Notification.query.filter_by(user_notification=False).all()]
    #         print("Operator Notifications in db:", db_notifications)
    #         print("Notifications written:", notifs)
    #         # make sure every operator got their notification
    #         for v in risky_visits:
    #             rid = v['restaurant_id']
    #             et = v['entrance_time']
    #             rnot = fetch_operator_notifications(app, rid)
    #             print(f"[{rid}] REST NOTIFICATION:", rnot)
    #             self.assertEqual(len(rnot), 1)
    #             self.assertEqual(rnot[0].date, et)

    #     self.assertEqual(len(db_notifications), nrisky_places)

    # def test_operator_notifications_sync(self):
    #     with app.app_context():
    #         positive_guy = User.query.filter_by(is_positive=True).first().to_dict()

    #         # generate positive user visits to random restaurants in last 14 days
    #         n_places = random.randrange(1, 10)
    #         nrisky_places, risky_visits = visit_random_places(app, positive_guy['id'], self.now,\
    #              INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS,time_span_offset=0)
    #         print(f"User {positive_guy['id']} visited {nrisky_places} restaurants")
    #         # generate other users visits to same restaurants in same days
    #         visits_per_rest = {}
    #         n_visits = random.randint(1, 3)
    #         for visit in risky_visits:
    #             rid = visit['restaurant_id']
    #             et = visit['entrance_time']
    #             visits_per_rest[rid] = add_random_visits_to_place(app, rid, et, et, et, n_visits)
    #             print(f"Some other {visits_per_rest[rid]} users visited restaurant {rid}")
    #         # execute pipeline async to generate notifications
    #         # run async tasks: check visited places -> check customers in danger -> write notifications
    #         pos_id = positive_guy['id']
    #         visited_places = check_visited_places(pos_id, INCUBATION_PERIOD_COVID)
    #         dang_res = contact_tracing(visited_places, pos_id)
    #         notifs = create_notifications(dang_res, pos_id)
            
    #         db_notifications = [n.to_dict() for n in Notification.query.filter_by(user_notification=False).all()]
    #         print("Operator Notifications in db:", db_notifications)
    #         print("Notifications written:", notifs)
    #         # make sure every operator got their notification
    #         for v in risky_visits:
    #             rid = v['restaurant_id']
    #             et = v['entrance_time']
    #             rnot = fetch_operator_notifications(app, rid)
    #             print(f"[{rid}] REST NOTIFICATION:", rnot)
    #             self.assertEqual(len(rnot), 1)
    #             self.assertEqual(rnot[0].date, et)

    #     self.assertEqual(len(db_notifications), nrisky_places)



    # def test_user_notifications(self):
    #     with app.app_context():
    #         positive_guy = User.query.filter_by(is_positive=True).first().to_dict()
    #         # generate positive user visits to random restaurants in last 14 days
    #         n_places = random.randrange(1, 10)
    #         nrisky_places, risky_visits = visit_random_places(app, positive_guy['id'], self.now, INCUBATION_PERIOD_COVID, n_places, RESTAURANT_TEST_IDS, time_span_offset=0)
    #         print(f"User {positive_guy['id']} visited {nrisky_places} restaurants")
    #         # generate other users visits to same restaurants in same days
    #         visits_per_rest = {}
    #         n_visits = random.randint(1, 3)
    #         other_users_visiting = list(range(1000, 1000+n_visits))
    #         print("USERS", other_users_visiting, n_visits)
    #         # each user makes a reservation to each restaurant visited by the positive guy
    #         for visit in risky_visits:
    #             rid = visit['restaurant_id']
    #             et = visit['entrance_time']
    #             visits_per_rest[rid] = add_random_visits_to_place(app, rid, et, et, et, n_visits, other_users_visiting)
    #             print(f"Some other {visits_per_rest[rid]} users visited restaurant {rid}")
    #         # execute pipeline async to generate notifications
    #         # run async tasks: check visited places -> check customers in danger -> write notifications
    #         pos_id = positive_guy['id']
    #         exec_chain = (check_visited_places.s(pos_id, INCUBATION_PERIOD_COVID) |
    #          contact_tracing.s(pos_id) | create_notifications.s(pos_id))()
            
    #         notifs = exec_chain.get()
    #         db_notifications = [n.to_dict() for n in Notification.query.filter_by(user_notification=True).all()]
    #         print("User Notifications in db:", db_notifications)
    #         # make sure every user got their notification
    #         for user_id in other_users_visiting:
    #             user_not = fetch_user_notifications(app, user_id)
    #             print(f"[{user_id}] USER NOTIFICATION:", [(u[0].to_dict(), u[1]) for u in user_not])
    #             self.assertEqual(len(user_not), len(risky_visits))
                

    #     # check that every user had their notifications generated
    #     self.assertEqual(len(db_notifications), sum(visits_per_rest.values()))

    # def test_notification_retrieval(self):
    #     with app.app_context():
    #         # create a notification and retrieve it by notification id
    #         n = Notification(user_id=10, positive_user_id=1, restaurant_id=12,
    #             date=datetime.now(), positive_user_reservation=1, user_notification=True)
    #         db.session.add(n)
    #         db.session.commit()
    #         notif_id = n.to_dict()['id']
    #         notif = getAndSetNotification(1)
    #         self.assertEqual(notif.id, notif_id)
    #         # then retrieve it by user
    #         user = User.query.get(10)
    #         notifs = fetch_notifications(app, user)
    #         self.assertDictEqual(notif.to_dict(), notifs[0].to_dict())
