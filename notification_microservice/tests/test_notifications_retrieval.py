import unittest
import random
from notification_microservice.database import Notification, db
from datetime import datetime
from notification_microservice.tests.utils import add_random_restaurants, create_app_for_test
from notification_microservice.notifications_fetch import *

app = create_app_for_test()
class NotificationRetrieval(unittest.TestCase):

    def setUp(self) -> None:
        self.tested_app = app.test_client()
        db.create_all(app=app)
        pass

    def tearDown(self) -> None:
        db.drop_all(app=app)
        pass

    def test_notification_by_id_api(self):
        # write a notification in db
        with app.app_context():
            n = Notification(user_id=2, positive_user_id=1, date=datetime.now(), positive_user_reservation=1, restaurant_id=1, user_notification=True)
            db.session.add(n)
            db.session.commit()
            not_id = Notification.query.get(1).id
            response = self.tested_app.get('/notifications/1').get_json()
            print(response)
            self.assertEqual(response['id'], not_id)

    def test_user_notification_fetch(self):
        # write some notifications
        uid = 10
        n_notifications = random.randint(0, 10)
        notifs = []
        with app.app_context():
            for _ in range(n_notifications):
                n = Notification(user_id=uid, positive_user_id=1, date=datetime.now(), positive_user_reservation=1, restaurant_id=1, user_notification=True)
                notifs.append(n)
            db.session.add_all(notifs)
            db.session.commit()
            notifs = self.tested_app.get(f'/notifications/user/{uid}').get_json()['notifications']
            db_notifs = [n.id for n in Notification.query.with_entities(Notification.id).all()]
            self.assertEqual(len(notifs), len(db_notifs))
            
            for notification in notifs:
                self.assertIn(notification['id'], db_notifs)

    def test_operator_notification_fetch(self):
        # write some restaurant notifications
        rid = 10
        n_notifications = random.randint(0, 10)
        notifs = []
        with app.app_context():
            for _ in range(n_notifications):
                n = Notification(user_id=random.randint(0, 100), positive_user_id=1, date=datetime.now(), positive_user_reservation=1, restaurant_id=rid, user_notification=False)
                notifs.append(n)
            db.session.add_all(notifs)
            db.session.commit()
            notifs = self.tested_app.get(f'/notifications/restaurant/{rid}').get_json()['notifications']
            db_notifs = [n.id for n in Notification.query.with_entities(Notification.id).all()]
            self.assertEqual(len(notifs), len(db_notifs))
            
            for notification in notifs:
                self.assertIn(notification['id'], db_notifs)

        



    