# auth_service.py
from hashing import verify_password, hash_password, needs_rehash

# Assuming you have some database object or ORM (like SQLAlchemy or Tortoise)
# from your_project.database import db, User


def login_user(username, provided_password):
    """
    Main logic to authenticate a user and upgrade their security if needed.
    """
    # 1. Look up the user in your database
    # Example: user = db.query(User).filter_by(username=username).first()
    user = get_user_from_db(username)  # This is your DB-specific function

    if not user:
        return {"status": "error", "message": "User not found"}

    # 2. Check the password
    # user.password_hash is what you stored in the DB previously
    if verify_password(provided_password, user.password_hash):

        # 3. UPGRADE LOGIC (Upgrade on Login)
        # If the hash is old (e.g., 260k iterations), we update it now
        if needs_rehash(user.password_hash):
            new_hash = hash_password(provided_password)
            # Update the user record in your DB
            update_user_password_in_db(user.id, new_hash)
            print(f"DEBUG: Security upgraded for user {username}")

        return {"status": "success", "message": "Access Granted"}

    return {"status": "error", "message": "Invalid password"}
