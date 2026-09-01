from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from supabase import Client
from core.supabase_client import get_supabase
from typing import Optional
import uuid

router = APIRouter(prefix="/storage", tags=["Storage"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    folder: Optional[str] = "default",
    supabase: Client = Depends(get_supabase)
):
    """Upload file to Supabase storage."""
    try:
        # Generate unique filename
        file_extension = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"{folder}/{file_name}"
        
        # Read file content
        file_content = await file.read()
        
        # Upload to Supabase
        response = supabase.storage.from_(
            supabase.config.get("SUPABASE_BUCKET_NAME", "agrishield-uploads")
        ).upload(file_path, file_content, {"content-type": file.content_type})
        
        # Get public URL
        public_url = supabase.storage.from_(
            supabase.config.get("SUPABASE_BUCKET_NAME", "agrishield-uploads")
        ).get_public_url(file_path)
        
        return {
            "file_name": file_name,
            "file_path": file_path,
            "public_url": public_url,
            "size": len(file_content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{file_path:path}")
async def delete_file(
    file_path: str,
    supabase: Client = Depends(get_supabase)
):
    """Delete file from Supabase storage."""
    try:
        supabase.storage.from_(
            supabase.config.get("SUPABASE_BUCKET_NAME", "agrishield-uploads")
        ).remove([file_path])
        
        return {"message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))