from sqlalchemy.orm import Session

from app.models.document import Document


def create_document(
    db: Session,
    *,
    user_id: int,
    title: str | None,
    image_path: str,
    ocr_image_path: str,
    ocr_result: dict,
) -> Document:
    document = Document(
        user_id=user_id,
        title=title,
        image_path=image_path,
        ocr_image_path=ocr_image_path,
        ocr_result=ocr_result,
        full_text=ocr_result.get("full_text", "") if isinstance(ocr_result, dict) else "",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session, user_id: int) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.updated_at.desc(), Document.id.desc())
        .all()
    )


def get_document(db: Session, document_id: int, user_id: int) -> Document | None:
    return (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )


def update_document(
    db: Session,
    document: Document,
    *,
    title: str | None = None,
    ocr_result: dict | None = None,
) -> Document:
    if title is not None:
        document.title = title
    if ocr_result is not None:
        document.ocr_result = ocr_result
        document.full_text = ocr_result.get("full_text", "") if isinstance(ocr_result, dict) else ""
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()
