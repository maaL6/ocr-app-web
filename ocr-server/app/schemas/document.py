from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    ocr_result: dict[str, Any] | None = None

    @field_validator("ocr_result")
    @classmethod
    def validate_ocr_result(cls, value):
        if value is None:
            return value
        required = {"full_text", "columns", "results", "preprocess"}
        missing = required.difference(value)
        if missing:
            raise ValueError(f"Thiếu dữ liệu OCR: {', '.join(sorted(missing))}")
        if not isinstance(value["full_text"], str):
            raise ValueError("full_text phải là chuỗi")
        if not isinstance(value["columns"], list) or not isinstance(value["results"], list):
            raise ValueError("columns và results phải là danh sách")
        return value


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    full_text: str
    created_at: datetime
    updated_at: datetime
    original_image_url: str
    ocr_image_url: str


class DocumentDetail(DocumentSummary):
    ocr_result: dict[str, Any]


class DeleteDocumentsResponse(BaseModel):
    deleted: int
