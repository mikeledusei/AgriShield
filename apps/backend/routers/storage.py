"""Secure file upload to Supabase Storage."""
import uuid

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from supabase import Client

from core.auth import get_current_user
from core.config import settings
from core.supabase_client import get_supabase

router = APIRouter(prefix="/storage", tags=["Storage"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    folder: str = "default",
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Upload file to Supabase storage (authenticated users only)."""
    try:
        file_extension = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"{folder}/{file_name}"

        file_content = await file.read()

        bucket_name = settings.SUPABASE_BUCKET_NAME
        supabase.storage.from_(bucket_name).upload(
            file_path, file_content, {"content-type": file.content_type}
        )

        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)

        return {
            "file_name": file_name,
            "file_path": file_path,
            "public_url": public_url,
            "size": len(file_content),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{file_path:path}")
async def delete_file(
    file_path: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Delete file from Supabase storage (authenticated users only)."""
    try:
        bucket_name = settings.SUPABASE_BUCKET_NAME
        supabase.storage.from_(bucket_name).remove([file_path])
        return {"message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
