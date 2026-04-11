import uuid
from sqlalchemy.orm import Session
import models, schemas, auth

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    user_id = str(uuid.uuid4())
    db_user = models.User(
        user_id=user_id,
        username=user.username,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_search_history(db: Session, user_id: str, query: str):
    db_history = models.SearchHistory(
        user_id=user_id,
        query=query
    )
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history
