from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.security import verify_access_token
from app.crud.admin import get_admin_by_id


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_admin(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Dependency: verify admin JWT token and return Admin object."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ",
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = verify_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    # Check role
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền admin",
        )

    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ",
        )

    admin = get_admin_by_id(db, int(admin_id))
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quản trị viên không tồn tại",
        )

    return admin
