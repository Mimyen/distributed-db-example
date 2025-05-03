from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_
from passlib.context import CryptContext
from collections import Counter
from typing import Literal, Optional, List, Tuple
from . import models, schemas

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_email_and_password(db: Session, email: str, password: str):
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user: return None

    if verify_password(password, user.hashed_password):
        return user
    else: return None

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = hash_password(user.password)
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user