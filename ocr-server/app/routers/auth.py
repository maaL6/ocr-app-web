from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.schemas.user import UserProfileUpdate, UserRegister
from app.schemas.auth import UserLogin, GoogleLogin
from app.dependencies import get_db
from app.crud.user import (
    create_user,
    create_user_from_google,
    get_user_by_email,
    get_user_by_google_id,
    get_user_by_id,
    update_user_profile,
)
from app.security import (
    create_access_token,
    verify_access_token,
    verify_google_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_current_user_from_token(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = verify_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ")

    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại")

    return user


@router.post("/register")
def register(
    user: UserRegister,
    db: Session = Depends(get_db),
):
    try:
        create_user(db, user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "message": "Đăng ký thành công"
    }


@router.post("/login")
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, str(payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    access_token = create_access_token(
        {"sub": str(user.id), "email": user.email, "fullname": user.fullname}
    )

    return {
        "message": "Đăng nhập thành công",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "fullname": user.fullname,
            "phone_number": user.phone_number,
        },
    }


@router.post("/google")
def google_login(
    payload: GoogleLogin,
    db: Session = Depends(get_db),
):
    # 1. Verify Google ID token
    try:
        id_info = verify_google_token(payload.id_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    google_id = id_info.get("sub")
    email = id_info.get("email", "")
    fullname = id_info.get("name", "")

    if not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token không chứa sub",
        )

    # 2. Tìm user theo google_id
    user = get_user_by_google_id(db, google_id)

    if not user:
        # 3. Kiểm tra email đã tồn tại chưa — nếu có thì link google_id
        existing = get_user_by_email(db, email) if email else None
        if existing:
            existing.google_id = google_id
            db.commit()
            db.refresh(existing)
            user = existing
        else:
            # 4. Tạo user mới từ Google
            user = create_user_from_google(db, google_id, email, fullname)

    # 5. Tạo JWT token
    access_token = create_access_token(
        {"sub": str(user.id), "email": user.email, "fullname": user.fullname}
    )

    return {
        "message": "Đăng nhập Google thành công",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "fullname": user.fullname,
            "phone_number": user.phone_number,
            "google_id": user.google_id,
        },
    }


@router.patch("/me")
def update_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    if payload.fullname is None and payload.phone_number is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không có dữ liệu để cập nhật")

    user = update_user_profile(db, current_user.id, payload)

    return {
        "message": "Cập nhật thành công",
        "user": {
            "id": user.id,
            "email": user.email,
            "fullname": user.fullname,
            "phone_number": user.phone_number,
        },
    }
