from app import create_app, db
from app.models import User, Account, Transaction
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Clear data
    Transaction.query.delete()
    Account.query.delete()
    User.query.delete()

    # Create a dummy admin user
    admin = User(
        username="admin123",
        name="Admin",
        email="admin@example.com",
        is_staff=True,
        is_admin=True
    )
    admin.set_password("admin123")

    # Add and commit
    db.session.add(admin)
    db.session.commit()
    
    customer = User(
        username="deva123",
        name="Deva",
        email="deva@example.com",
        is_staff=False
    )
    customer.set_password("deva123")
    db.session.add(customer)
    db.session.commit()
    print("✅ Test customer created: deva@example.com / deva123")



    print("✅ All user-related data reset.")
    print("✅ Admin user created: admin@example.com / admin123")
