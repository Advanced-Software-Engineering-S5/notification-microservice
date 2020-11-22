from datetime import datetime, timedelta, time
import logging
from notification_microservice.background import celery
from notification_microservice.database import Notification
import requests, os
from notification_microservice.database import db

# tasks are written so that pipeline|chain async execution is easily implemented

@celery.task
def check_visited_places(userid: int, day_range: int):
    """ Checks the restaurants in which a given customer has been to
        in the last `day_range` days.
    Args:
        userid (int): Id of the customer
        day_range (int): Number of days in which we're checking the customer activities.
    Returns:
        [type]: A list of restaurants reservations or an empty list in case the customer didn't visit
        any restaurant.
    """
    print(f"Checking visited places by user {userid} in the last {day_range} days")
    # get reservations in which user actually showed up from Reservation service
    range_ = datetime.now() - timedelta(days=day_range)
    range_.replace(hour=0, minute=0, second=0, microsecond=0)
    
    response = requests.get(f'http://{os.environ.GOS_RESERVATION}/filtered_reservations/{userid}?start_time={range_.isoformat()}')
    if response.status_code != 200:
        # error in server
        return []
    reservations = response.json()['reservations']

    # reservations = Reservation.query.filter_by(user_id=userid).\
    # filter(Reservation.entrance_time != None).filter(Reservation.entrance_time >= range).all()
    # print("DB", db)
    # also all results must be json serializable
    return reservations

@celery.task
def create_notifications(reservation_at_riks, positive_id: int):
    """
        Writes positive contact notifications to database, both for other customers as well as operator.
    Args:
        reservation_at_riks ([type]): List of dictionaries, each containing a reservation made by a user which was
        possibly in contact with a positive customer.
        positive_id (str): identifier of the positive customer.
    """
    # create multiple notification even if the user visited the same restaurant in multiple occasions
    notifications = []
    # hence one operator notification per positive user reservation/visit
    pos_user_reservations = []
    for reservation in reservation_at_riks:
        rest_id = reservation['restaurant_id']
        customer_id = reservation['user_id']
        pos_res = reservation['positive_user_reservation']

        # when function is called without celery, there's no need to serialize to JSON
        et = reservation['entrance_time']
        # entrance time of user receiving notification, not positive guy one
        if isinstance(et, str):
            et = datetime.strptime(reservation['entrance_time'], '%Y-%m-%dT%H:%M:%S.%f')
        
        # create notification for the user
        notification = Notification(positive_user_id=positive_id, restaurant_id=rest_id,
        date=et, user_id = customer_id, positive_user_reservation=pos_res, user_notification=True, email_sent=False)
        # create notification for the operator
        if not pos_res in pos_user_reservations:
            # operator_id = User.query.filter_by(restaurant_id=rest_id).first()
            operator_notification = Notification(positive_user_id=positive_id, restaurant_id=rest_id,
            date=et, positive_user_reservation=pos_res, user_notification=False, email_sent=False)
            pos_user_reservations.append(pos_res)
            notifications.append(operator_notification)

        notifications.append(notification)
    # store in database
    db.session.add_all(notifications)
    db.session.commit()
    return [n.to_dict() for n in notifications]  

@celery.task
def contact_tracing(past_reservations, user_id: int):
    """Given a positive user id and a list of past reservation he/she made in the last 14 days,
        returns a list of reservation made by other users which were allegedly in contact with him/her.

    Args:
        past_reservations: List of dictionaries, each representing a reservation the positive 
        user made.
        user_id (int): Positive customer id.
    """
    # check which users were at the restaurant at the same time as the positive guy
    reservation_at_risk = []
    for reservation in past_reservations:
        et = reservation['entrance_time']
        if isinstance(et, str):
            et = datetime.strptime(reservation['entrance_time'], '%Y-%m-%dT%H:%M:%S.%f')
        # avg_stay_time = Restaurant.query.filter_by(id=reservation['restaurant_id']).first().avg_stay_time
        # get average staying time of the restaurant from Restaurant service and compute 'danger period'
        resp = requests.get(f"http://{os.environ.get('GOS_RESTAURANT')}/restaurants/{reservation['restaurant_id']}")
        if resp == 404:
            # restaurant does not exists/was deleted, carry on defining a standard avg time (prioritize reservations which are always kept)
            avg_stay_time = time(hour=1, minute=30)
        else:
            avg_stay_time = resp.json()['avg_stay_time']
            # convert time format back to object
            avg_stay_time = datetime.strptime(avg_stay_time, "%H:%M:%S").time()

        staying_interval = timedelta(hours=avg_stay_time.hour, minutes=avg_stay_time.minute, seconds=avg_stay_time.second)
        start_time = et - staying_interval
        end_time = et + staying_interval
        # now get reservations booked in same 'danger' period as the positive guy ones
        response = requests.get(f'http://{os.environ.GOS_RESERVATION}/filtered_reservations/{user_id}?\
            restaurant_id={reservation["restaurant_id"]}&start_time={start_time.isoformat()}&end_time={end_time.isoformat()}&exclude_user_id=true')
        if response.status_code != 200:
            # error in server
            continue
        user_reservation = response.json()['reservations']
        # user_reservation = Reservation.query.filter(Reservation.user_id != user_id).\
            # filter_by(restaurant_id=reservation['restaurant_id']).\
                # filter(Reservation.entrance_time.between(start_time, end_time)).all()
        # print(user_reservation)
        # preserve positive user reservation we're referring to, as to notify operator 
        for u in user_reservation:
            u['positive_user_reservation'] = reservation['id']
            reservation_at_risk.append(u)

    return reservation_at_risk
