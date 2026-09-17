import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import STORAGE_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE


class UploadValidationError(Exception):
    pass


def validate_upload(file: UploadFile, size: int):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Format file '{ext}' tidak didukung. Gunakan PDF, JPG, atau PNG."
        )
    if size > MAX_UPLOAD_SIZE:
        raise UploadValidationError(
            f"Ukuran file melebihi batas maksimum ({MAX_UPLOAD_SIZE // (1024*1024)} MB)."
        )
    return ext


def save_upload_file(case_id: str, file: UploadFile, raw_bytes: bytes) -> dict:
    """Simpan file upload ke storage lokal, dikelompokkan per case_id."""
    ext = Path(file.filename).suffix.lower()
    case_dir = STORAGE_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = case_dir / stored_filename

    with open(dest_path, "wb") as f:
        f.write(raw_bytes)

    return {
        "stored_filename": stored_filename,
        "storage_path": str(dest_path),
        "file_format": ext.lstrip("."),
        "file_size": len(raw_bytes),
    }


def delete_file(storage_path: str):
    p = Path(storage_path)
    if p.exists():
        p.unlink()
