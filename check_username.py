from app import create_app
from app.models import User

app = create_app()

with app.app_context():
    email = "deva@bank.com"
    mobile = "8714140366"

    user = User.query.filter(
        ((User.email == email) | (User.mobile_number == mobile)) & (User.is_staff == True)
    ).first()

    if user:
        print(f"Your username is: {user.username}")
    else:
        print("No staff user found with that email or mobile number.")
