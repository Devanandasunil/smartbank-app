# reset_users.py

from app import create_app, db
from app.models import User, Account, Transaction  # ✅ removed Goal

app = create_app()

with app.app_context():
    Transaction.query.delete()
    Account.query.delete()
    User.query.delete()
    db.session.commit()
    print("✅ All user-related data reset.")

