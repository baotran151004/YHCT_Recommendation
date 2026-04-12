from sqlalchemy.orm import Session
import models, schemas, auth

def get_user_by_username(db: Session, username: str):
    """Retrieve a user by their unique username."""
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Create a new user with a hashed password."""
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str):
    """Verify user credentials and return the user if successful."""
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not auth.verify_password(password, user.hashed_password):
        return False
    return user

def save_search(db: Session, user_id: int, query: str):
    """Save a search query to the user's history."""
    db_history = models.SearchHistory(
        user_id=user_id,
        query=query
    )
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history

def get_user_history(db: Session, user_id: int):
    """Retrieve search history for a specific user, sorted by most recent."""
    return db.query(models.SearchHistory).filter(models.SearchHistory.user_id == user_id).order_by(models.SearchHistory.created_at.desc()).all()
