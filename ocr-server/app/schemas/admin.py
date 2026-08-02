from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr


# ============================================================
# Auth
# ============================================================

class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminInfo(BaseModel):
    id: int
    name: str
    email: str
    avatar_url: str | None = None
    created_at: str


# ============================================================
# Users
# ============================================================

class AdminUserResponse(BaseModel):
    id: int
    fullname: str
    email: str
    avatar_url: str | None = None
    is_online: bool
    last_seen: str | None = None
    created_at: str
    is_locked: bool


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]
    total: int
    page: int
    total_pages: int


class AdminLockRequest(BaseModel):
    locked: bool


# ============================================================
# Documents
# ============================================================

class AdminDocumentResponse(BaseModel):
    id: int
    user_id: int
    owner_name: str
    title: str | None = None
    full_text: str
    created_at: str
    updated_at: str
    original_image_url: str
    ocr_image_url: str
    ocr_result: dict[str, Any]


class AdminDocumentListResponse(BaseModel):
    documents: list[AdminDocumentResponse]
    total: int
    page: int
    total_pages: int


class AdminBulkDeleteRequest(BaseModel):
    doc_ids: list[int]


class AdminBulkDeleteResponse(BaseModel):
    success: bool
    deleted_count: int


class AdminExportRequest(BaseModel):
    scope: str  # "all" | "user" | "multiple" | "single"
    user_id: int | None = None
    doc_ids: list[int] | None = None
    doc_id: int | None = None


# ============================================================
# Stats
# ============================================================

class AdminTopUser(BaseModel):
    user_id: int
    fullname: str
    count: int


class AdminMonthlyRegistration(BaseModel):
    month: str
    count: int


class AdminStatsResponse(BaseModel):
    total_users: int
    online_count: int
    total_docs: int
    docs_today: int
    users_today: int
    avg_confidence: float
    success_rate: float
    top_users: list[AdminTopUser]
    monthly_registrations: list[AdminMonthlyRegistration]


# ============================================================
# Settings
# ============================================================

class AdminSettingsResponse(BaseModel):
    allow_registration: bool
    allow_google_login: bool
    max_image_size_mb: int
    max_images_per_user: int
    maintenance_mode: bool
    maintenance_message: str
    dark_mode: bool


class AdminSettingsUpdate(BaseModel):
    allow_registration: bool | None = None
    allow_google_login: bool | None = None
    max_image_size_mb: int | None = None
    max_images_per_user: int | None = None
    maintenance_mode: bool | None = None
    maintenance_message: str | None = None
    dark_mode: bool | None = None


# ============================================================
# Logs
# ============================================================

class AdminLogResponse(BaseModel):
    id: int
    action: str
    admin_name: str
    target: str
    timestamp: str


class AdminLogListResponse(BaseModel):
    logs: list[AdminLogResponse]
    total: int


# ============================================================
# Notifications
# ============================================================

class AdminNotificationResponse(BaseModel):
    id: int
    message: str
    type: str
    read: bool
    timestamp: str


class AdminNotificationReadResponse(BaseModel):
    success: bool
    notification: AdminNotificationResponse | None = None