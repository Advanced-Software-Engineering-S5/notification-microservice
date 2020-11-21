import requests
from notification_microservice.tests.utils import create_app_for_test 
import unittest, datetime
from notification_microservice.database import db, Notification
from notification_microservice.classes.mail_task import send_contact_notification
from notification_microservice.background import make_celery
from celery.contrib.testing.worker import start_worker
import os
 
app = create_app_for_test()
class TestMail(unittest.TestCase):

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
        with app.app_context():

            user1 = dict(firstname="user1",
                 lastname="user1",
                 email="user1@example.com",
                #  email="nicolo.lucchesi@gmail.com",
                 phone='324455123',
                 password="user1",
                 dateofbirth=datetime.date(2020, 10, 31).isoformat())

            user2 = dict(firstname="user2",
                 lastname="user2",
                 email="user2@example.com", #This is the recipient mail address
                 phone='324455321',
                 password="user2",
                 dateofbirth=datetime.date(2020, 10, 31).isoformat())
            self.users = [user1, user2]
            self.uids = []

    def tearDown(self):
        db.drop_all(app=app)
        # delete users created in User service
        for id in self.uids:
            resp = requests.delete(f"http://{os.environ.get('GOS_USER')}/users/{id}")


    def test_send_mail(self):
        with app.app_context():
            n_users = 2
            # create some users
            self.uids = [requests.post(f'http://{os.environ.get("GOS_USER")}/user', json=self.users[i]).json() for i in range(n_users)]
            print('user ids:', self.uids)

            # create some fake notifications
            for i, uid in enumerate(self.uids):
                n = Notification(positive_user_id = 20, date = datetime.date(2020, 10, 31),
                             user_id = uid, positive_user_reservation = 1,
                             restaurant_id = 1, user_notification = True)
                db.session.add(n)
            db.session.commit()

            send_contact_notification.delay().get()

            #check the notification has the field email_sent correctly set to true
            self.assertEqual(len(Notification.query.filter_by(email_sent=True).all()), n_users)
            self.assertEqual(len(Notification.query.filter_by(email_sent=False).all()), 0)

    def test_send_mail_fail(self):
        # send email to undefined user (id=-1) to test failure in response
        with app.app_context():
            n = Notification(positive_user_id = 20, date = datetime.date(2020, 10, 31),
                                user_id = -1, positive_user_reservation = 1,
                                restaurant_id = 1, user_notification = True)
            db.session.add(n)
            db.session.commit()

            send_contact_notification.delay().forget()

            #check the notification hasn't the field email_sent set
            self.assertEqual(len(Notification.query.filter_by(email_sent=True).all()), 0)
            self.assertEqual(len(Notification.query.filter_by(email_sent=False).all()), 1)