import pickle
import numpy as np
from yourapp import create_app, db
from yourapp.models import User

app = create_app()  # or your app factory
app.app_context().push()

def is_valid_encoding(enc):
    return isinstance(enc, np.ndarray) and enc.shape == (128,)

def cleanup_broken_face_encodings(delete=False):
    broken_users = []
    users = User.query.filter_by(is_staff=True).all()

    for user in users:
        if user.face_encoding:
            try:
                enc = pickle.loads(user.face_encoding)
                if not is_valid_encoding(enc):
                    print(f"Invalid encoding shape for user {user.username}: {type(enc)} {getattr(enc, 'shape', None)}")
                    broken_users.append(user)
            except Exception as e:
                print(f"Error unpickling encoding for user {user.username}: {e}")
                broken_users.append(user)

    print(f"\nFound {len(broken_users)} users with broken face encodings.\n")

    if delete and broken_users:
        confirm = input("Are you sure you want to DELETE these users? Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            for user in broken_users:
                print(f"Deleting user {user.username} with broken encoding...")
                db.session.delete(user)
            db.session.commit()
            print("Deleted all broken users.")
        else:
            print("Deletion cancelled.")
    else:
        print("Deletion not enabled. Run with delete=True to remove broken users.")

if __name__ == "__main__":
    cleanup_broken_face_encodings(delete=False)  # Change to True to delete users
