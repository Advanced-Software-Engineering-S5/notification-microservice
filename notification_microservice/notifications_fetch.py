from datetime import datetime, timedelta
from database import Notification, Restaurant, User, db
from flask import Flask
from sqlalchemy import desc, distinct

def fetch_user_notifications(app: Flask, user_id: int, unread_only=False):
    """Retrieve 'positive case contact' notifications of user identified by `user_id`.
    Args:
        app (Flask): flask app.
        user_id (int): identifier of user requesting notifications.
        unread_only (bool, optional): Whether to retrieve unread notifications only. Defaults to False.
    """
    with app.app_context():
        query = Notification.query.filter_by(user_id=user_id, user_notification=True)
        # get restaurant too
        if unread_only:
            query = query.filter_by(notification_checked=False)

        query = query.join(Restaurant).with_entities(Notification, Restaurant)

        query = query.order_by(desc(Notification.date))
        
        return query.all()

def fetch_operator_notifications(app:Flask, rest_id: int, unread_only=False):
    # get notifications belonging to a certain restaurant
    with app.app_context():
        # query = Reservation.query.join(Notification)\
        query = Notification.query.filter_by(restaurant_id=rest_id, user_notification=False)
            
        if unread_only:
            query = query.filter_by(notification_checked=False)

        # query = query.with_entities(Reservation, Notification)
        query = query.order_by(desc(Notification.date))

        # return [q.to_dict() for q in query.all()]
        return query.all()

def fetch_notifications(app: Flask, user: User, unread_only=False):
    """Fetch notifications of operator or user alike.
    Args:
        app (Flask): flask app for context.
        user_id ([type]): id of the user to retrieve notifications of.
    """
    if hasattr(user, 'restaurant_id') and not user.restaurant_id is None:
        return fetch_operator_notifications(app, user.restaurant_id, unread_only)
    else:
        user_not = fetch_user_notifications(app, user.id, unread_only)
        # add restaurant info
        notifications = []
        for notif, restaurant in user_not:
            notif.restaurant = restaurant
            notifications.append(notif)
        return notifications

def getAndSetNotification(notification_id: int):
    """ Fetch specific notification by id and sets its state to
       'read' if the notification was unread.
    Args:
        notification_id (int): id of the notification to retrieve.

    Returns:
        [type]: Notification object requested.
    """
    notification = Notification.query.filter_by(id=notification_id).join(Restaurant).with_entities(Notification, Restaurant).first()
    if notification[0].notification_checked == False:
        notification[0].notification_checked = True
        db.session.commit()
    notif = notification[0]
    notif.restaurant = notification[1]
    return notif