from flask import request
import logging 

def new_positive_case(user_id: int):
    from notification_microservice.classes.notifications_tasks import check_visited_places, contact_tracing, create_notifications
    # starts new positive case contact tracing background task
    ndays = request.args.get('incubation_period', 14)
    if not isinstance(ndays, int) or ndays <= 0: 
        ndays = 14
    print(f'New positive case:{user_id}, starting background task')
    try:
        exec_chain = (check_visited_places.s(user_id, ndays) |
             contact_tracing.s(user_id) | create_notifications.s(user_id))()
        return {}, 200
    except Exception as e:
        logging.error(e)
        return {}, 500