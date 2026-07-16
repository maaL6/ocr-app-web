import json
import mimetypes

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.crud.document import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    update_document,
)
from app.dependencies import get_db
from app.document_storage import (
    delete_document_images,
    resolve_image_path,
    save_document_images,
)
from app.routers.auth import get_current_user_from_token
from app.schemas.document import (
    DeleteDocumentsResponse,
    DocumentDetail,
    DocumentSummary,
    DocumentUpdate,
)


router = APIRouter(prefix="/documents", tags=["Documents"])
MAX_OCR_JSON_BYTES = 10 * 1024 * 1024


def _validate_ocr_result(raw: str) -> dict:
    if len(raw.encode("utf-8")) > MAX_OCR_JSON_BYTES:
        raise HTTPException(status_code=413, detail="Kết quả OCR vượt quá dung lượng cho phép")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="ocr_result_json không hợp lệ") from exc

    try:
        validated = DocumentUpdate(ocr_result=value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return validated.ocr_result or {}


def _summary(document) -> dict:
    result = document.ocr_result or {}
    return {
        "id": document.id,
        "title": document.title,
        "full_text": str(result.get("full_text", "")),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "original_image_url": f"/documents/{document.id}/image/original",
        "ocr_image_url": f"/documents/{document.id}/image/ocr",
    }


def _detail(document) -> dict:
    return {**_summary(document), "ocr_result": document.ocr_result or {}}


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
async def create_document_endpoint(
    title: str | None = Form(default=None, max_length=255),
    ocr_result_json: str = Form(...),
    original_image: UploadFile = File(...),
    ocr_image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    ocr_result = _validate_ocr_result(ocr_result_json)
    image_path, ocr_image_path = await save_document_images(
        user_id=current_user.id,
        original_image=original_image,
        ocr_image=ocr_image,
    )

    try:
        document = create_document(
            db,
            user_id=current_user.id,
            title=title,
            image_path=image_path,
            ocr_image_path=ocr_image_path,
            ocr_result=ocr_result,
        )
    except Exception:
        db.rollback()
        delete_document_images(image_path, ocr_image_path)
        raise
    return _detail(document)


@router.get("", response_model=list[DocumentSummary])
def list_documents_endpoint(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    return [_summary(item) for item in list_documents(db, current_user.id)]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document_endpoint(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    document = get_document(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    return _detail(document)


@router.patch("/{document_id}", response_model=DocumentDetail)
def update_document_endpoint(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    if payload.title is None and payload.ocr_result is None:
        raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật")

    document = get_document(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    return _detail(
        update_document(
            db,
            document,
            title=payload.title,
            ocr_result=payload.ocr_result,
        )
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    document = get_document(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    image_paths = (document.image_path, document.ocr_image_path)
    delete_document(db, document)
    delete_document_images(*image_paths)


@router.delete("", response_model=DeleteDocumentsResponse)
def delete_all_documents_endpoint(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    documents = list_documents(db, current_user.id)
    paths = [(item.image_path, item.ocr_image_path) for item in documents]
    for document in documents:
        db.delete(document)
    db.commit()
    for image_paths in paths:
        delete_document_images(*image_paths)
    return {"deleted": len(documents)}


@router.get("/{document_id}/image/{image_kind}")
def get_document_image(
    document_id: int,
    image_kind: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_token),
):
    document = get_document(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")

    if image_kind == "original":
        relative_path = document.image_path
    elif image_kind == "ocr":
        relative_path = document.ocr_image_path
    else:
        raise HTTPException(status_code=404, detail="Loại ảnh không hợp lệ")

    path = resolve_image_path(relative_path)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store"},
    )
