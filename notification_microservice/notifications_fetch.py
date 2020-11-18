from datetime import datetime, timedelta
from notification_microservice.database import Notification, Restaurant, User, db
from sqlalchemy import desc, distinct
from flask import request
import requests
import os

empty_restaurant_response = {
    "avg_stars": 0.,
    "avg_stay_time": "-",
    "id": -1,
    "lat": 0.0,
    "lon": 0.0,
    "name": "-",
    "num_reviews": 0,
    "phone": "-"
}
def fetch_user_notifications(user_id: int):
    """Retrieve 'positive case contact' notifications of user identified by `user_id`.
    Args:
        user_id (int): identifier of user requesting notifications.
        unread_only (bool, optional): Whether to retrieve unread notifications only. Defaults to False.
    """
    unread_only = request.args.get('unread_only', False)
    try:
        query = Notification.query.filter_by(user_id=user_id, user_notification=True)
        if unread_only:
            query = query.filter_by(notification_checked=False)
        notifications = query.order_by(desc(Notification.date)).all()
    except:
        return {'message': 'Error accessing database'}, 500

    # join notifications results with corresponding restaurants by querying restaurant microservice
    try:
        response = requests.post(f'{os.environ.get("GOS_RESTAURANT")}/restaurants/', 
            json={'restaurant_ids': [n.restaurant_id for n in notifications]})
        # handle failed response by providing notification information only
        restaurants = [] if response.status_code != 200 else response.json()['restaurants']
        # use dict for faster lookups
        restaurants = {r['id']: r for r in restaurants}
    except:
        restaurants = {}

    # query = query.join(Restaurant).with_entities(Notification, Restaurant)
    # format response
    notifs_with_rests = []
    for notif in notifications:
        n = notif.to_dict_with_keys(['id', 'date', 'notification_checked', 'user_id', 'restaurant_id'])
        n['restaurant'] = restaurants.get(n['restaurant_id'], empty_restaurant_response)
        notifs_with_rests.append(n)
    return {'notifications': notifs_with_rests}

def fetch_operator_notifications(restaurant_id: int):
    """ Get notifications belonging to a certain restaurant/operator.

    Args:
        rest_id (int): id of the restaurant of which we want to see notifications of.
        unread_only (bool, optional): Whether to retrieve unread notifications only. Defaults to False.
    Returns:
        [type]: [description]
    """
    unread_only = request.args.get('unread_only', False)
    try:
        query = Notification.query.filter_by(restaurant_id=restaurant_id, user_notification=False)
            
        if unread_only:
            query = query.filter_by(notification_checked=False)

        # query = query.with_entities(Reservation, Notification)
        query = query.order_by(desc(Notification.date))
        notifs = [q.to_dict_with_keys(['id', 'date', 'notification_checked', 'user_id', 'restaurant_id']) for q in query.all()]
    except:
        return {'message': 'Error accessing database'}, 500

    # operator doesn't need info about their restaurant
    return {'notifications': notifs}

def getAndSetNotification(notification_id: int):
    """ Fetch specific notification by id and sets its state to
       'read' if the notification was unread.
    Args:
        notification_id (int): id of the notification to retrieve.

    Returns:
        [type]: Notification object requested.
    """
    try:
        notification = Notification.query.filter_by(id=notification_id).first()
    except:
        return {'message': 'Error accessing database'}, 500
    if notification is None:
        return {'message': 'Requested notification does not exist'}, 404

    # get restaurant information too if service is available
    try:
        response = requests.post(f'{os.environ.get("GOS_RESTAURANT")}/restaurants/{notification.restaurant_id}')
        print("REST RESP", response)
        # handle failed response by providing notification information only
        restaurant = empty_restaurant_response if response.status_code != 200 else response.json()
    except:
        restaurant = empty_restaurant_response

    notif = notification.to_dict_with_keys(['id', 'date', 'notification_checked', 'user_id', 'restaurant_id'])
    if notification.notification_checked == False:
        notification.notification_checked = True
        notif['notification_checked'] = True
        try:
            db.session.commit()
        except:
            return {'message': 'Error accessing database'}, 500

    notif['restaurant'] = restaurant
    return notif