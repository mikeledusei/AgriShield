"""Auth API: register, login, me."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from supabase import Client

from core.auth import get_current_user
from core.supabase_client import get_supabase

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: str = "farmer"   # farmer | government | admin


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, sb: Client = Depends(get_supabase)):
    try:
        resp = sb.auth.sign_up({
            "email": req.email,
            "password": req.password,
            "options": {"data": {"full_name": req.full_name, "role": req.role}},
        })
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Registration failed: {exc}")
    if resp.user is None:
        raise HTTPException(status_code=400, detail="Registration failed.")
    return {"id": resp.user.id, "email": resp.user.email,
            "full_name": req.full_name, "role": req.role,
            "requires_email_verification": resp.user.identities == [] or len(resp.user.identities) == 0}


@router.post("/login")
def login(req: LoginRequest, sb: Client = Depends(get_supabase)):
    try:
        resp = sb.auth.sign_in_with_password({"email": req.email, "password": req.password})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if resp.session is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    meta = resp.user.user_metadata or {}
    return {
        "access_token": resp.session.access_token,
        "refresh_token": resp.session.refresh_token,
        "token_type": "bearer",
        "user": {"id": resp.user.id, "email": resp.user.email,
                 "full_name": meta.get("full_name"), "role": meta.get("role", "farmer")},
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
