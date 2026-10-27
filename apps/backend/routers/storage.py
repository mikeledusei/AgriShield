"""Secure file upload to Supabase Storage."""
from pathlib import Path
import re
import uuid

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from supabase import Client

from core.auth import get_current_user
from core.config import settings
from core.supabase_client import get_supabase

router = APIRouter(prefix="/storage", tags=["Storage"])

ALLOWED_STORAGE_EXTS = {"csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"}
SAFE_FOLDER_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    folder: str = "default",
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Upload file to Supabase storage (authenticated users only)."""
    clean_folder = folder.strip() or "default"
    if not SAFE_FOLDER_RE.match(clean_folder):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage folder name.",
        )

    raw_name = (file.filename or "").strip()
    file_extension = Path(raw_name).suffix.lower().lstrip(".")
    if not file_extension or file_extension not in ALLOWED_STORAGE_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported or missing file extension.",
        )

    file_content = await file.read()
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(file_content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum size limit of 10 MB.",
        )

    file_name = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"{clean_folder}/{file_name}"

    try:
        bucket_name = settings.SUPABASE_BUCKET_NAME
        supabase.storage.from_(bucket_name).upload(
            file_path,
            file_content,
            {"content-type": file.content_type or "application/octet-stream"},
        )
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        return {
            "file_name": file_name,
            "file_path": file_path,
            "public_url": public_url,
            "size": len(file_content),
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage upload failed.",
        )


@router.delete("/delete/{file_path:path}")
async def delete_file(
    file_path: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Delete file from Supabase storage (authenticated users only)."""
    normalized = file_path.strip().lstrip("/")
    if not normalized or ".." in normalized.split("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage file path.",
        )
    try:
        bucket_name = settings.SUPABASE_BUCKET_NAME
        supabase.storage.from_(bucket_name).remove([normalized])
        return {"message": "File deleted successfully"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Storage delete failed.",
        )
