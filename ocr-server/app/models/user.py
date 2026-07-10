from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, nullable=False)

    fullname = Column(String, nullable=False)

    password_hash = Column(String, nullable=False)

    phone_number = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())