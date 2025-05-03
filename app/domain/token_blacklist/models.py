from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, event, Text, DateTime
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from app.config import IP_ADDRESS
from ..model_base import Base

class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    token = Column(String, primary_key=True, unique=True)
    expiration_date = Column(DateTime, nullable=False)
