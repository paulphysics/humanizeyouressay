# make_admin.py
import sys
from humanizer_app import create_app, db
from humanizer_app.models import User

app = create_app()

with app.app_context():
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py user@example.com")
        sys.exit(1)

    admin_email = sys.argv[1]

    user = User.query.filter_by(email=admin_email).first()

    if user:
        user.is_admin = True
        db.session.commit()
        print(f"✅ Successfully made {admin_email} an admin.")
    else:
        print(f"❌ User with email {admin_email} not found.")
