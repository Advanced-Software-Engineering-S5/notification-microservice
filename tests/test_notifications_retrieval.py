import unittest
import random
from database import Notification, db
from datetime import datetime
from tests.utils import add_random_restaurants, create_app_for_test
from notifications_fetch import *

app = create_app_for_test()
class NotificationRetrieval(unittest.TestCase):

    def setUp(self) -> None:
        # db.create_all(app=app)
        pass

    def tearDown(self) -> None:
        # db.drop_all(app=app)
        pass

    def test_user_notification_fetching(self):
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
            add_random_restaurants(1, app)
            notifs = fetch_user_notifications(app, uid, unread_only=False)
            db_notifs = [n.id for n in Notification.query.with_entities(Notification.id).all()]
            self.assertEqual(len(notifs), len(db_notifs))
            
            for notification, rest in notifs:
                self.assertIn(notification.id, db_notifs)

        



    