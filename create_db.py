from app import db, create_app

app = create_app()  # if you have a factory function, else just import your app

with app.app_context():
    db.create_all()
    print("Database tables created successfully!")
