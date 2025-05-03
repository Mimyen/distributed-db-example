from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_
from passlib.context import CryptContext
from collections import Counter
from typing import Literal, Optional, List, Tuple
from . import models, schemas


def get_blacklist_token(db: Session, token: schemas.BlacklistTokenElement):
    return db.query(models.TokenBlacklist).filter(models.TokenBlacklist.token == token.token).first()

def get_blacklist_tokens(db: Session):
    return db.query(models.TokenBlacklist).all()

def create_blacklist_token(db: Session, token: schemas.BlacklistTokenElementFull):
    db_blacklist_token = models.TokenBlacklist(
        token=token.token,
        expiration_date=token.expiration_date
    )
    db.add(db_blacklist_token)
    db.commit()
    db.refresh(db_blacklist_token)
    return db_blacklist_token

def delete_blacklist_token(db: Session, token: schemas.BlacklistTokenElement):
    try:
        db.delete(get_blacklist_token(db, token))
        db.commit()
        return True
    except Exception as e:
        print(e)
        return False