from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from . import db, login_manager
from datetime import datetime
import random
from werkzeug.security import generate_password_hash, check_password_hash
import enum

# -- Flask-Login user loader --
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -- Enum for Saving Modes --
class SavingMode(enum.Enum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

# -- User Model --
class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(150))
    place = db.Column(db.String(150), nullable=True)
    mobile_number = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    profile_image = db.Column(db.String(200), nullable=True)
    is_staff = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    face_encoding = db.Column(db.LargeBinary, nullable=True)

    account = db.relationship('Account', backref='user', uselist=False)
    loans = db.relationship('Loan', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    goals = db.relationship('FinancialGoal', backref='user', lazy=True)
    
    # Relationships for spam reports
    spam_reports_sent = db.relationship('SpamReport', foreign_keys='SpamReport.user_id', backref='reporter', lazy=True)
    spam_reports_received = db.relationship('SpamReport', foreign_keys='SpamReport.reported_user_id', backref='reported_user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"

    def terminate_account(self, permanent=False):
        if permanent:
            db.session.delete(self)
        else:
            # Handle soft deletion logic (e.g., flag user as inactive)
            self.is_active = False
        db.session.commit()

# -- Utility: Generate Unique Account Number --
def generate_account_number():
    for _ in range(10):
        acc_num = str(random.randint(1000000000, 9999999999))
        if not Account.query.filter_by(account_number=acc_num).first():
            return acc_num
    raise Exception("Failed to generate a unique account number")

# -- Account Model --
class Account(db.Model):
    __tablename__ = 'account'

    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False, default=generate_account_number)
    balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# -- Financial Goal Model --
class FinancialGoal(db.Model):
    __tablename__ = "financial_goal"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_amount = db.Column(db.Float)
    deadline = db.Column(db.Date)
    saving_mode = db.Column(db.Enum(SavingMode), default=SavingMode.NONE, nullable=False)
    daily_amount = db.Column(db.Float, default=0.0)
    weekly_amount = db.Column(db.Float, default=0.0)
    monthly_amount = db.Column(db.Float, default=0.0)
    yearly_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Goal ₹{self.target_amount} by {self.deadline}>"

# -- Transaction Model --
class Transaction(db.Model):
    __tablename__ = 'transaction'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20))
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_account = db.Column(db.String(20), nullable=True)
    is_fraud = db.Column(db.Boolean, default=False)
    reported = db.Column(db.Boolean, default=False)

    spam_reports = db.relationship('SpamReport', backref='transaction', lazy=True)

    def __repr__(self):
        return f"<Transaction {self.type} ₹{self.amount}>"

# -- Loan Model --
class Loan(db.Model):
    __tablename__ = 'loan'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float)
    reason = db.Column(db.String(255))
    status = db.Column(db.String(20), default='Pending')
    emi_due = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f"<Loan ₹{self.amount} - {self.status}>"

# -- Spam Report Model --
class SpamReport(db.Model):
    __tablename__ = 'spam_report'

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reason = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SpamReport Transaction {self.transaction_id}>"

