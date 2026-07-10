from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.security import hash_password


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, data):

    # 1. CHECK TRÙNG EMAIL
    existing_user = get_user_by_email(db, data.email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng"
        )

    # 2. CREATE USER
    user = User(
        email=data.email,
        fullname=data.fullname,
        password_hash=hash_password(data.password),
        phone_number=data.phone_number,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def update_user_profile(db: Session, user_id: int, data):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại")

    if data.fullname is not None:
        user.fullname = data.fullname
    if data.phone_number is not None:
        user.phone_number = data.phone_number

    db.commit()
    db.refresh(user)
    return user