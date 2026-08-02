from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, nullable=False)

    fullname = Column(String, nullable=False)

    password_hash = Column(String, nullable=True)

    google_id = Column(String, unique=True, index=True, nullable=True)

    phone_number = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    is_locked = Column(Boolean, default=False, nullable=False)

    last_seen = Column(DateTime)

    is_online = Column(Boolean, default=False, nullable=False)

    avatar_url = Column(Text)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
