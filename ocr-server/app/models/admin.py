from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    fullname = Column(String(255), nullable=False)
    avatar_url = Column(Text)
    permissions = Column(JSON, default=list, nullable=False)
    is_super = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"))
    action = Column(String(255), nullable=False)
    target = Column(Text, nullable=False)
    metadata = Column(JSONB, default=dict, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)
    read = Column(Boolean, default=False, nullable=False)
    metadata = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, default=1)
    allow_registration = Column(Boolean, default=True, nullable=False)
    allow_google_login = Column(Boolean, default=True, nullable=False)
    max_image_size_mb = Column(Integer, default=10, nullable=False)
    max_images_per_user = Column(Integer, default=100, nullable=False)
    maintenance_mode = Column(Boolean, default=False, nullable=False)
    maintenance_message = Column(Text, default="", nullable=False)
    dark_mode = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)