from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    positive_user_id = db.Column(db.Integer)
    date = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, nullable=True)
    # user = relationship('User', foreign_keys='Notification.user_id')

    positive_user_reservation = db.Column(db.Integer)
    restaurant_id = db.Column(db.Integer)
    notification_checked = db.Column(db.Boolean, default=False)
    email_sent = db.Column(db.Boolean, default=False)
    
    user_notification = db.Column(db.Boolean) # belongs to a user or operator

    def to_dict(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
    
    def to_dict_with_keys(self, keys):
        notif = {}
        for column in keys:
            val = getattr(self, column)
            if isinstance(val, datetime):
                val = str(val.isoformat())
            notif[column] = val
            
        return notif