import hashlib
import os
from datetime import datetime, timedelta, timezone

from pathlib import Path

from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests

from jose import JWTError, jwt

load_dotenv(Path(__file__).resolve().parent / ".env")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-me")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


def hash_password(password: str):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password, hashed):
    return hash_password(password) == hashed


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Token không hợp lệ") from exc


def verify_google_token(token: str) -> dict:
    """Verify Google ID token and return the decoded info."""
    try:
        id_info = id_token.verify_oauth2_token(
            token, requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError as exc:
        raise ValueError("Google token không hợp lệ") from exc

    if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
        raise ValueError("Google token issuer không hợp lệ")

    return id_info
