# make_admin.py
from humanizer_app import create_app, db
from humanizer_app.models import User

# Create a Flask app instance
app = create_app()

with app.app_context():
    # The email of the user to make admin
    admin_email = "paulokoth37@gmail.com"

    # Find the user by email
    user = User.query.filter_by(email=admin_email).first()

    if user:
        # Set the is_admin flag to True
        user.is_admin = True
        db.session.commit()
        print(f"Successfully made {admin_email} an admin.")
    else:
        print(f"User with email {admin_email} not found.")
