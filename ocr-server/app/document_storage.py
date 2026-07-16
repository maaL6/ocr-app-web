import io
import os
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image


UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "/code/data/uploads")).resolve()
MAX_IMAGE_BYTES = int(os.getenv("MAX_DOCUMENT_IMAGE_BYTES", str(25 * 1024 * 1024)))

IMAGE_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "TIFF": ".tiff",
}


async def _read_image(upload: UploadFile) -> tuple[bytes, str]:
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Ảnh vượt quá dung lượng cho phép",
        )

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            extension = IMAGE_EXTENSIONS.get(image.format or "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="File tải lên không phải ảnh hợp lệ") from exc

    if not extension:
        raise HTTPException(status_code=400, detail="Định dạng ảnh không được hỗ trợ")
    return data, extension


async def save_document_images(
    *,
    user_id: int,
    original_image: UploadFile,
    ocr_image: UploadFile,
) -> tuple[str, str]:
    original_data, original_extension = await _read_image(original_image)
    ocr_data, ocr_extension = await _read_image(ocr_image)

    relative_directory = Path("users") / str(user_id) / "documents" / uuid.uuid4().hex
    absolute_directory = UPLOAD_ROOT / relative_directory
    absolute_directory.mkdir(parents=True, exist_ok=False)

    original_relative = relative_directory / f"original{original_extension}"
    ocr_relative = relative_directory / f"ocr{ocr_extension}"

    try:
        (UPLOAD_ROOT / original_relative).write_bytes(original_data)
        (UPLOAD_ROOT / ocr_relative).write_bytes(ocr_data)
    except Exception:
        shutil.rmtree(absolute_directory, ignore_errors=True)
        raise

    return original_relative.as_posix(), ocr_relative.as_posix()


def resolve_image_path(relative_path: str | None) -> Path:
    if not relative_path:
        raise HTTPException(status_code=404, detail="Ảnh không tồn tại")

    path = (UPLOAD_ROOT / relative_path).resolve()
    if not path.is_relative_to(UPLOAD_ROOT) or not path.is_file():
        raise HTTPException(status_code=404, detail="Ảnh không tồn tại")
    return path


def delete_document_images(*relative_paths: str | None) -> None:
    directories: set[Path] = set()
    for relative_path in relative_paths:
        if not relative_path:
            continue
        path = (UPLOAD_ROOT / relative_path).resolve()
        if path.is_relative_to(UPLOAD_ROOT):
            directories.add(path.parent)

    for directory in directories:
        shutil.rmtree(directory, ignore_errors=True)
