import csv
import io
import json
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_admin
from app.crud.admin import (
    get_admin_by_email,
    get_admin_by_id,
    update_admin_last_login,
    list_admin_users,
    get_admin_user,
    toggle_lock_user,
    get_user_documents,
    get_user_document_count,
    list_admin_documents,
    get_admin_document,
    delete_admin_document,
    bulk_delete_documents,
    get_all_documents_for_export,
    get_admin_stats,
    get_or_create_settings,
    update_settings,
    list_admin_logs,
    write_log,
    list_notifications,
    mark_notification_read,
)
from app.models.admin import Admin
from app.models.user import User
from app.models.document import Document
from app.schemas.admin import (
    AdminLogin,
    AdminLockRequest,
    AdminBulkDeleteRequest,
    AdminExportRequest,
    AdminSettingsUpdate,
)
from app.security import create_admin_access_token, verify_password

router = APIRouter(prefix="/admin", tags=["Admin"])


def _admin_info(admin: Admin) -> dict:
    return {
        "id": admin.id,
        "name": admin.fullname,
        "email": admin.email,
        "avatar_url": admin.avatar_url,
        "created_at": admin.created_at.isoformat() if admin.created_at else "",
    }


def _log_action(db: Session, admin: Admin, action: str, target: str, request: Request | None = None):
    """Helper to write admin log. Uses a sub-transaction so logging failures
    don't roll back the main operation."""
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
    try:
        savepoint = db.begin_nested()
        try:
            write_log(db, admin.id, action, target, ip_address=ip, user_agent=ua)
            savepoint.commit()
        except Exception:
            savepoint.rollback()
            db.rollback()  # rollback just this savepoint, not the whole session
            raise
    except Exception:
        db.rollback()


# ============================================================
# 1. AUTH
# ============================================================

@router.post("/auth/login")
def admin_login(
    payload: AdminLogin,
    db: Session = Depends(get_db),
):
    admin = get_admin_by_email(db, str(payload.email))
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    update_admin_last_login(db, admin)

    token = create_admin_access_token(
        {"sub": str(admin.id), "email": admin.email, "fullname": admin.fullname}
    )

    return {
        "token": token,
        "admin": _admin_info(admin),
    }


# ============================================================
# 2. DASHBOARD
# ============================================================

@router.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return get_admin_stats(db)


@router.get("/me")
def admin_me(
    admin: Admin = Depends(get_current_admin),
):
    """Return info for the currently authenticated admin."""
    return _admin_info(admin)


@router.get("/dashboard/notifications")
def dashboard_notifications(
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return list_notifications(db, admin.id)


@router.post("/notifications/{notif_id}/read")
def read_notification(
    notif_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    result = mark_notification_read(db, notif_id, admin.id)
    if not result:
        raise HTTPException(status_code=404, detail="Thông báo không tồn tại")
    return {"success": True, "notification": result}


# ============================================================
# 3. USERS
# ============================================================

@router.get("/users")
def list_users(
    query: str | None = Query(default=None),
    filter_online: str = Query(default="all"),
    page: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return list_admin_users(db, query, filter_online, page, limit)


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    user = get_admin_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    return user


@router.patch("/users/{user_id}/lock")
def lock_user(
    user_id: int,
    payload: AdminLockRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    result = toggle_lock_user(db, user_id, payload.locked)
    if not result:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

    action = "Khóa tài khoản" if payload.locked else "Mở khóa tài khoản"
    _log_action(db, admin, action, result["fullname"], request)

    return result


@router.get("/users/{user_id}/documents")
def user_documents(
    user_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return get_user_documents(db, user_id)


@router.get("/users/{user_id}/documents/count")
def user_document_count(
    user_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return {"count": get_user_document_count(db, user_id)}


# ============================================================
# 4. DOCUMENTS
# ============================================================

@router.get("/documents")
def list_documents(
    query: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    min_confidence: float | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return list_admin_documents(
        db, query, user_id, min_confidence, date_from, date_to, page, limit
    )


@router.get("/documents/{doc_id}")
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    doc = get_admin_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
    return doc


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    doc = get_admin_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")

    delete_admin_document(db, doc_id)
    _log_action(db, admin, "Xóa ảnh", f"Ảnh ID {doc_id}", request)

    return {"success": True}


@router.delete("/documents/bulk")
def bulk_delete(
    payload: AdminBulkDeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    deleted = bulk_delete_documents(db, payload.doc_ids)
    _log_action(db, admin, "Xóa hàng loạt", f"{deleted} ảnh", request)
    return {"success": True, "deletedCount": deleted}


@router.post("/documents/export")
def export_documents(
    payload: AdminExportRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    docs = get_all_documents_for_export(
        db,
        scope=payload.scope,
        user_id=payload.user_id,
        doc_ids=payload.doc_ids,
        doc_id=payload.doc_id,
    )

    _log_action(db, admin, "Tải dữ liệu", f"Export {len(docs)} ảnh", request)

    # Create ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Manifest
        manifest = {
            "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
            "scope": payload.scope,
            "total_docs": len(docs),
        }
        zf.writestr("training_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        for doc in docs:
            user = db.query(User).filter(User.id == doc.user_id).first()
            owner = user.fullname if user else f"user_{doc.user_id}"
            safe_title = (doc.title or f"doc_{doc.id}").replace(" ", "_")
            folder = f"user_{doc.user_id}_{owner}/doc_{doc.id}_{safe_title}"

            ocr_result = doc.ocr_result or {}
            zf.writestr(
                f"{folder}/{safe_title}_result.json",
                json.dumps(ocr_result, indent=2, ensure_ascii=False),
            )

            # Try to include images if paths exist
            if doc.image_path:
                try:
                    from app.document_storage import resolve_image_path
                    path = resolve_image_path(doc.image_path)
                    zf.write(path, f"{folder}/{safe_title}_original.jpg")
                except Exception:
                    pass

            if doc.ocr_image_path:
                try:
                    from app.document_storage import resolve_image_path
                    path = resolve_image_path(doc.ocr_image_path)
                    zf.write(path, f"{folder}/{safe_title}_ocr.jpg")
                except Exception:
                    pass

    buf.seek(0)

    filename = f"training_export_{len(docs)}_docs.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================
# 5. STATS EXPORT
# ============================================================

@router.get("/stats/export")
def stats_export(
    format: str = Query(default="csv"),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    stats = get_admin_stats(db)

    if format == "json":
        return stats

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Thông số", "Giá trị"])
    writer.writerow(["Tổng user", stats["totalUsers"]])
    writer.writerow(["Online", stats["onlineCount"]])
    writer.writerow(["Tổng ảnh", stats["totalDocs"]])
    writer.writerow(["Ảnh hôm nay", stats["docsToday"]])
    writer.writerow(["User hôm nay", stats["usersToday"]])
    writer.writerow(["Điểm tin cậy TB", f"{stats['avgConfidence'] * 100:.1f}%"])
    writer.writerow(["Tỷ lệ thành công", f"{stats['successRate'] * 100:.1f}%"])
    writer.writerow([])
    writer.writerow(["Tháng", "Đăng ký"])
    for m in stats["monthlyRegistrations"]:
        writer.writerow([m["month"], m["count"]])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stats_report.csv"},
    )


# ============================================================
# 6. SETTINGS
# ============================================================

@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    settings = get_or_create_settings(db)
    return {
        "allowRegistration": settings.allow_registration,
        "allowGoogleLogin": settings.allow_google_login,
        "maxImageSizeMB": settings.max_image_size_mb,
        "maxImagesPerUser": settings.max_images_per_user,
        "maintenanceMode": settings.maintenance_mode,
        "maintenanceMessage": settings.maintenance_message,
        "darkMode": settings.dark_mode,
    }


@router.patch("/settings")
def patch_settings(
    payload: AdminSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    updates = payload.model_dump(exclude_none=True)
    settings = update_settings(db, updates)
    _log_action(db, admin, "Cập nhật cài đặt", ", ".join(updates.keys()) or "settings", request)
    return {
        "allowRegistration": settings.allow_registration,
        "allowGoogleLogin": settings.allow_google_login,
        "maxImageSizeMB": settings.max_image_size_mb,
        "maxImagesPerUser": settings.max_images_per_user,
        "maintenanceMode": settings.maintenance_mode,
        "maintenanceMessage": settings.maintenance_message,
        "darkMode": settings.dark_mode,
    }


# ============================================================
# 7. LOGS
# ============================================================

@router.get("/logs")
def list_logs(
    query: str | None = Query(default=None),
    action: str | None = Query(default=None),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    page: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    return list_admin_logs(db, query, action, from_date, to_date, page, limit)