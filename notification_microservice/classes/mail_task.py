from notification_microservice.background import celery
from notification_microservice.database import db, Notification
import requests, logging, os
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
import os

env = Environment(loader=FileSystemLoader('%s/../templates/' % os.path.dirname(__file__)))
@celery.task
def send_contact_notification():
    """
        This task is triggered periodically, checks users at risk and sends them
        an email in case they haven't received one yet.
    """
    logging.info("Mail sending..")
    notifications = Notification.query.filter_by(email_sent=False, user_notification=True).all()
    count = 0
    for notification in notifications:
        user_id = notification.user_id
        # fetch user mail from User service
        try:
            # print('request to:',f"http://{os.environ.get('GOS_USER')}/user?id={user_id}")
            resp = requests.get(f"http://{os.environ.get('GOS_USER')}/user?id={user_id}")
            if resp.status_code != 200:
                logging.error(f"[{resp.status_code}] Mail task, User service replied with error {resp.json()}")
                continue
            email = resp.json()['email']
        except Exception as e:
            # if user requests fails, we'll try to send email at next task trigger
            logging.error(e)
            continue
        if email is not None and email.strip() != '':
            # send email
            date = notification.date.strftime('%Y-%m-%d at %H:%M')
            template = env.get_template('./mail_notification.html')
            output = template.render(dest=resp.json(), date=date)
            pos_outcome = send_email(email, output)
            if pos_outcome:
                notification.email_sent = True
                db.session.commit()
                logging.info(f"Email to {email} just sent")
                count += 1
            else:
                logging.error(f"Error while sending email to {email}")

    logging.info(f'{count} email(s) sent')

# @celery.task
def send_email(to_email, bodyContent):
    logging.info(f'Sending email to {to_email}..')
    from_email = 'GoOutSafe.ase@gmail.com'
    subject = 'GoOutSafe contact notification'
    message = MIMEMultipart()
    message['Subject'] = subject
    message['From'] = from_email
    message['To'] = to_email

    message.attach(MIMEText(bodyContent, "html"))
    msgBody = message.as_string()

    logging.info(f'Sending email to {to_email}')
    # don't actually send emails to example.com...
    if (to_email.find("@example.com") == -1):
        try:
            server = SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(from_email, 'AseSquad5')
            server.sendmail(from_email, to_email, msgBody)
            server.quit()
        except Exception as e:
            logging.error(e)
            return False
    return True

@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    logging.info("Configuring crono task..")
    # Register the unmark_all as crono task
    # sender.add_periodic_task(60.0 * 60.0, unmark_all.s(14), name='unmark_positive')
    #Register the send_mail task
    sender.add_periodic_task(30.0, send_contact_notification.s(), name="send_emails")