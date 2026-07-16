from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.routers.auth import router as auth_router
from app.security import (
    create_access_token,
    hash_password,
    verify_access_token,
    verify_password,
)


def test_password_hashing_round_trip():
    password = "123456"
    hashed = hash_password(password)

    assert hashed
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_round_trip():
    token = create_access_token({"sub": "1", "email": "user@example.com"})

    payload = verify_access_token(token)

    assert payload["sub"] == "1"
    assert payload["email"] == "user@example.com"


def test_login_returns_access_token(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(auth_router)

    class DummyUser:
        id = 1
        email = "user@example.com"
        fullname = "Test User"
        phone_number = "0123456789"
        password_hash = hash_password("123456")

    def override_get_db():
        yield object()

    monkeypatch.setattr("app.routers.auth.get_user_by_email", lambda db, email: DummyUser())
    monkeypatch.setattr("app.routers.auth.verify_password", lambda password, hashed: True)

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as client:
        response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "123456"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "user@example.com"

    test_app.dependency_overrides.clear()


def test_profile_update_requires_auth(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(auth_router)

    class DummyUser:
        id = 1
        email = "user@example.com"
        fullname = "Test User"
        phone_number = "0123456789"

    def override_get_db():
        yield object()

    monkeypatch.setattr("app.routers.auth.get_user_by_id", lambda db, user_id: DummyUser())
    monkeypatch.setattr("app.routers.auth.verify_access_token", lambda token: {"sub": "1"})

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as client:
        response = client.patch(
            "/auth/me",
            headers={"Authorization": "Bearer test-token"},
            json={"fullname": "Updated User", "phone_number": "0999999999"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["fullname"] == "Updated User"
    assert body["user"]["phone_number"] == "0999999999"

    test_app.dependency_overrides.clear()
