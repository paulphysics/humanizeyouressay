import uuid
from humanizer_app import create_app, db
from humanizer_app.models import User

# Create a Flask app instance to get the application context
app = create_app()

def backfill_codes():
    with app.app_context():
        # Find all users who do not have a referral code yet
        users_without_codes = User.query.filter(User.referral_code == None).all()
        
        if not users_without_codes:
            print("All users already have referral codes. Nothing to do.")
            return

        print(f"Found {len(users_without_codes)} users without referral codes. Backfilling now...")

        for user in users_without_codes:
            # Generate a new, unique referral code for each user
            user.referral_code = f"REF-{str(uuid.uuid4())[:8].upper()}"
            print(f"Generated code {user.referral_code} for user {user.email}")

        # Commit all the changes to the database
        db.session.commit()
        print("Successfully backfilled all missing referral codes!")

if __name__ == "__main__":
    backfill_codes()
