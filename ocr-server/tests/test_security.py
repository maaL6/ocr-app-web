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

    def mock_update_profile(db, user_id, data):
        user = DummyUser()
        user.fullname = data.fullname
        user.phone_number = data.phone_number
        return user

    monkeypatch.setattr("app.routers.auth.get_user_by_id", lambda db, user_id: DummyUser())
    monkeypatch.setattr("app.routers.auth.update_user_profile", mock_update_profile)
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


def test_google_login_new_user(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(auth_router)

    class DummyUser:
        id = 123
        email = "googleuser@example.com"
        fullname = "Google User"
        phone_number = None
        google_id = "google-sub-123"

    class MockDB:
        def commit(self):
            pass
        def refresh(self, obj):
            pass

    def override_get_db():
        yield MockDB()

    # Mock the verification and CRUD operations
    monkeypatch.setattr(
        "app.routers.auth.verify_google_token",
        lambda token: {
            "sub": "google-sub-123",
            "email": "googleuser@example.com",
            "name": "Google User",
            "iss": "accounts.google.com"
        }
    )
    monkeypatch.setattr(
        "app.routers.auth.get_user_by_google_id",
        lambda db, google_id: None
    )
    monkeypatch.setattr(
        "app.routers.auth.get_user_by_email",
        lambda db, email: None
    )
    monkeypatch.setattr(
        "app.routers.auth.create_user_from_google",
        lambda db, google_id, email, fullname: DummyUser()
    )

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as client:
        response = client.post(
            "/auth/google",
            json={"id_token": "mock-valid-google-token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["google_id"] == "google-sub-123"
    assert body["user"]["email"] == "googleuser@example.com"

    test_app.dependency_overrides.clear()


def test_google_login_existing_user(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(auth_router)

    class DummyUser:
        id = 456
        email = "existinguser@example.com"
        fullname = "Existing User"
        phone_number = "0987654321"
        google_id = None  # initially None, will be set by endpoint

    class MockDB:
        def commit(self):
            pass
        def refresh(self, obj):
            pass

    def override_get_db():
        yield MockDB()

    dummy_user = DummyUser()

    monkeypatch.setattr(
        "app.routers.auth.verify_google_token",
        lambda token: {
            "sub": "google-sub-456",
            "email": "existinguser@example.com",
            "name": "Existing User",
            "iss": "accounts.google.com"
        }
    )
    monkeypatch.setattr(
        "app.routers.auth.get_user_by_google_id",
        lambda db, google_id: None
    )
    monkeypatch.setattr(
        "app.routers.auth.get_user_by_email",
        lambda db, email: dummy_user
    )

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as client:
        response = client.post(
            "/auth/google",
            json={"id_token": "mock-valid-google-token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert dummy_user.google_id == "google-sub-456"

    test_app.dependency_overrides.clear()


def test_google_login_invalid_token(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(auth_router)

    def mock_verify_fail(token):
        raise ValueError("Google token không hợp lệ")

    monkeypatch.setattr("app.routers.auth.verify_google_token", mock_verify_fail)

    with TestClient(test_app) as client:
        response = client.post(
            "/auth/google",
            json={"id_token": "invalid-token"}
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Google token không hợp lệ"

