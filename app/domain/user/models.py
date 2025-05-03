from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, event, Text
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from app.config import IP_ADDRESS
from ..model_base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)


