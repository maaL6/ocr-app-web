# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    fullname: str
    password: str
    phone_number: str | None = None


class UserProfileUpdate(BaseModel):
    fullname: str | None = None
    phone_number: str | None = None
    avatar_url: str | None = None