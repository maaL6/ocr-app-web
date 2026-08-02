from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, text, String
from sqlalchemy.orm import Session

from app.models.admin import Admin, AdminLog, AdminNotification, AdminSetting
from app.models.user import User
from app.models.document import Document
from app.security import hash_password, verify_password


# ============================================================
# Admin Auth
# ============================================================

def get_admin_by_email(db: Session, email: str) -> Admin | None:
    return db.query(Admin).filter(Admin.email == email).first()


def get_admin_by_id(db: Session, admin_id: int) -> Admin | None:
    return db.query(Admin).filter(Admin.id == admin_id).first()


def update_admin_last_login(db: Session, admin: Admin) -> Admin:
    admin.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(admin)
    return admin


# ============================================================
# Users
# ============================================================

def _is_user_online(user: User) -> bool:
    if user.is_online:
        return True
    if not user.last_seen:
        return False
    # last_seen within 5 minutes
    now = datetime.utcnow()
    if user.last_seen.tzinfo is not None:
        now = datetime.now(timezone.utc)
    delta = now - user.last_seen
    return delta.total_seconds() < 300  # 5 minutes


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "fullname": user.fullname,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "is_online": _is_user_online(user),
        "last_seen": user.last_seen.isoformat() if user.last_seen else None,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "is_locked": user.is_locked,
    }


def list_admin_users(
    db: Session,
    query: str | None = None,
    filter_online: str = "all",
    page: int = 0,
    limit: int = 10,
) -> dict:
    q = db.query(User)

    if filter_online == "online":
        # online if last_seen < 5 min ago
        threshold = datetime.utcnow() - timedelta(minutes=5)
        q = q.filter(or_(User.is_online == True, User.last_seen >= threshold))
    elif filter_online == "offline":
        threshold = datetime.utcnow() - timedelta(minutes=5)
        q = q.filter(
            User.is_online == False,
            or_(User.last_seen < threshold, User.last_seen == None),
        )

    if query and query.strip():
        q_str = query.strip().lower()
        q = q.filter(
            or_(
                func.lower(User.fullname).contains(q_str),
                func.lower(User.email).contains(q_str),
                func.cast(User.id, String).contains(q_str),
            )
        )

    total = q.count()
    total_pages = max((total + limit - 1) // limit, 1)

    # Sort: online first, then by id ascending
    all_users = q.all()
    all_users.sort(key=lambda u: (not _is_user_online(u), u.id))

    start = page * limit
    end = start + limit
    page_users = all_users[start:end]

    return {
        "users": [_user_to_dict(u) for u in page_users],
        "total": total,
        "page": page,
        "totalPages": total_pages,
    }


def get_admin_user(db: Session, user_id: int) -> dict | None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    return _user_to_dict(user)


def toggle_lock_user(db: Session, user_id: int, locked: bool) -> dict | None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.is_locked = locked
    db.commit()
    db.refresh(user)
    return _user_to_dict(user)


def get_user_documents(db: Session, user_id: int) -> list[dict]:
    docs = (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_doc_to_dict(d, db) for d in docs]


def get_user_document_count(db: Session, user_id: int) -> int:
    return db.query(Document).filter(Document.user_id == user_id).count()


# ============================================================
# Documents
# ============================================================

def _doc_to_dict(doc: Document, db: Session) -> dict:
    # Get owner name
    user = db.query(User).filter(User.id == doc.user_id).first()
    owner_name = user.fullname if user else "Unknown"

    ocr_result = doc.ocr_result or {}
    full_text = doc.full_text or str(ocr_result.get("full_text", ""))

    # Build image URLs
    original_url = doc.original_image_url or f"/documents/{doc.id}/image/original"
    ocr_url = doc.ocr_image_url or f"/documents/{doc.id}/image/ocr"

    return {
        "id": doc.id,
        "user_id": doc.user_id,
        "owner_name": owner_name,
        "title": doc.title,
        "full_text": full_text,
        "created_at": doc.created_at.isoformat() if doc.created_at else "",
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else "",
        "original_image_url": original_url,
        "ocr_image_url": ocr_url,
        "ocr_result": ocr_result,
    }


def list_admin_documents(
    db: Session,
    query: str | None = None,
    user_id: int | None = None,
    min_confidence: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 0,
    limit: int = 10,
) -> dict:
    q = db.query(Document)

    if user_id is not None:
        q = q.filter(Document.user_id == user_id)

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            q = q.filter(Document.created_at >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            q = q.filter(Document.created_at <= dt_to)
        except ValueError:
            pass

    if query and query.strip():
        q_str = query.strip().lower()
        # Join with users for owner_name search
        q = q.outerjoin(User, Document.user_id == User.id)
        q = q.filter(
            or_(
                func.cast(Document.id, String).contains(q_str),
                func.lower(User.fullname).contains(q_str),
                func.lower(func.coalesce(Document.title, "")).contains(q_str),
                func.lower(func.coalesce(Document.full_text, "")).contains(q_str),
            )
        )

    total = q.count()
    total_pages = max((total + limit - 1) // limit, 1)

    q = q.order_by(Document.created_at.desc())
    start = page * limit
    page_docs = q.offset(start).limit(limit).all()

    # Filter by confidence (post-query since it's inside JSONB)
    result_docs = []
    for doc in page_docs:
        if min_confidence is not None:
            ocr_result = doc.ocr_result or {}
            results = ocr_result.get("results", [])
            first_conf = results[0].get("confidence", 0) if results else 0
            if first_conf < min_confidence / 100:
                continue
        result_docs.append(doc)

    return {
        "documents": [_doc_to_dict(d, db) for d in result_docs],
        "total": total,
        "page": page,
        "totalPages": total_pages,
    }


def get_admin_document(db: Session, doc_id: int) -> dict | None:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return None
    return _doc_to_dict(doc, db)


def delete_admin_document(db: Session, doc_id: int) -> bool:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return False
    db.delete(doc)
    db.commit()
    return True


def bulk_delete_documents(db: Session, doc_ids: list[int]) -> int:
    deleted = 0
    for doc_id in doc_ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            db.delete(doc)
            deleted += 1
    db.commit()
    return deleted


def get_all_documents_for_export(
    db: Session,
    scope: str = "all",
    user_id: int | None = None,
    doc_ids: list[int] | None = None,
    doc_id: int | None = None,
) -> list[Document]:
    q = db.query(Document)
    if scope == "single" and doc_id:
        q = q.filter(Document.id == doc_id)
    elif scope == "user" and user_id:
        q = q.filter(Document.user_id == user_id)
    elif scope == "multiple" and doc_ids:
        q = q.filter(Document.id.in_(doc_ids))
    return q.all()


# ============================================================
# Stats
# ============================================================

def get_admin_stats(db: Session) -> dict:
    total_users = db.query(User).count()
    total_docs = db.query(Document).count()

    # Online count
    threshold = datetime.utcnow() - timedelta(minutes=5)
    online_count = (
        db.query(User)
        .filter(or_(User.is_online == True, User.last_seen >= threshold))
        .count()
    )

    # Today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    docs_today = (
        db.query(Document)
        .filter(Document.created_at >= today_start)
        .count()
    )
    users_today = (
        db.query(User)
        .filter(User.created_at >= today_start)
        .count()
    )

    # Avg confidence & success rate
    all_docs = db.query(Document).all()
    total_confidence = 0.0
    success_docs = 0
    for doc in all_docs:
        ocr_result = doc.ocr_result or {}
        results = ocr_result.get("results", [])
        if results:
            total_confidence += results[0].get("confidence", 0)
        full_text = doc.full_text or ocr_result.get("full_text", "")
        if full_text.strip():
            success_docs += 1

    avg_confidence = total_confidence / len(all_docs) if all_docs else 0.0
    success_rate = success_docs / len(all_docs) if all_docs else 0.0

    # Top users by document count
    top_users_raw = (
        db.query(Document.user_id, func.count(Document.id).label("count"))
        .group_by(Document.user_id)
        .order_by(text("count DESC"))
        .limit(5)
        .all()
    )
    top_users = []
    for row in top_users_raw:
        user = db.query(User).filter(User.id == row.user_id).first()
        if user:
            top_users.append({
                "user_id": user.id,
                "fullname": user.fullname,
                "count": row.count,
            })

    # Monthly registrations (last 6 months)
    monthly = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        d = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        d = d.replace(month=d.month - i) if d.month - i >= 1 else d.replace(year=d.year - 1, month=d.month - i + 12)
        month_start = d
        if d.month == 12:
            month_end = d.replace(year=d.year + 1, month=1)
        else:
            month_end = d.replace(month=d.month + 1)

        count = (
            db.query(User)
            .filter(User.created_at >= month_start, User.created_at < month_end)
            .count()
        )
        label = f"Tháng {d.month}/{d.year}"
        monthly.append({"month": label, "count": count})

    return {
        "totalUsers": total_users,
        "onlineCount": online_count,
        "totalDocs": total_docs,
        "docsToday": docs_today,
        "usersToday": users_today,
        "avgConfidence": avg_confidence,
        "successRate": success_rate,
        "topUsers": [
            {"userId": u["user_id"], "fullname": u["fullname"], "count": u["count"]}
            for u in top_users
        ],
        "monthlyRegistrations": monthly,
    }


# ============================================================
# Settings
# ============================================================

def get_settings(db: Session) -> AdminSetting | None:
    return db.query(AdminSetting).filter(AdminSetting.id == 1).first()


def get_or_create_settings(db: Session) -> AdminSetting:
    settings = get_settings(db)
    if not settings:
        settings = AdminSetting(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, updates: dict) -> AdminSetting:
    settings = get_or_create_settings(db)
    for key, value in updates.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings


# ============================================================
# Logs
# ============================================================

def list_admin_logs(
    db: Session,
    query: str | None = None,
    action: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 0,
    limit: int = 20,
) -> dict:
    q = db.query(AdminLog)

    if action:
        q = q.filter(AdminLog.action == action)

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            q = q.filter(AdminLog.created_at >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            q = q.filter(AdminLog.created_at <= dt)
        except ValueError:
            pass

    if query and query.strip():
        q_str = query.strip().lower()
        # Join with admins table to search admin_name
        q = q.outerjoin(Admin, AdminLog.admin_id == Admin.id)
        q = q.filter(
            or_(
                func.lower(AdminLog.action).contains(q_str),
                func.lower(AdminLog.target).contains(q_str),
                func.lower(func.coalesce(Admin.fullname, "Unknown")).contains(q_str),
            )
        )

    total = q.count()
    q = q.order_by(AdminLog.created_at.desc())
    start = page * limit
    logs = q.offset(start).limit(limit).all()

    result_logs = []
    for log in logs:
        admin = db.query(Admin).filter(Admin.id == log.admin_id).first() if log.admin_id else None
        result_logs.append({
            "id": log.id,
            "action": log.action,
            "admin_name": admin.fullname if admin else "Unknown",
            "target": log.target,
            "timestamp": log.created_at.isoformat() if log.created_at else "",
        })

    return {"logs": result_logs, "total": total}


def write_log(
    db: Session,
    admin_id: int,
    action: str,
    target: str,
    metadata: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AdminLog:
    log = AdminLog(
        admin_id=admin_id,
        action=action,
        target=target,
        metadata=metadata or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# ============================================================
# Notifications
# ============================================================

def list_notifications(db: Session, admin_id: int) -> list[dict]:
    notifs = (
        db.query(AdminNotification)
        .filter(AdminNotification.admin_id == admin_id)
        .order_by(AdminNotification.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "message": n.message,
            "type": n.type,
            "read": n.read,
            "timestamp": n.created_at.isoformat() if n.created_at else "",
        }
        for n in notifs
    ]


def mark_notification_read(db: Session, notif_id: int, admin_id: int) -> dict | None:
    notif = (
        db.query(AdminNotification)
        .filter(
            AdminNotification.id == notif_id,
            AdminNotification.admin_id == admin_id,
        )
        .first()
    )
    if not notif:
        return None
    notif.read = True
    db.commit()
    db.refresh(notif)
    return {
        "id": notif.id,
        "message": notif.message,
        "type": notif.type,
        "read": notif.read,
        "timestamp": notif.created_at.isoformat() if notif.created_at else "",
    }


