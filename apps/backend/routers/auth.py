from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from core.supabase_client import get_supabase
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


class SignUpRequest(BaseModel):
    email: str
    password: str
    farmer_name: str | None = None
    phone: str | None = None


class SignInRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignUpRequest, supabase: Client = Depends(get_supabase)):
    """Register a new farmer/user."""
    try:
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "farmer_name": request.farmer_name,
                    "phone": request.phone,
                    "role": "farmer"
                }
            }
        })
        
        if not response.user:
            raise HTTPException(status_code=400, detail="Signup failed")
        
        return TokenResponse(
            access_token=response.session.access_token if response.session else "",
            refresh_token=response.session.refresh_token if response.session else "",
            user=response.user.dict()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/signin", response_model=TokenResponse)
async def signin(request: SignInRequest, supabase: Client = Depends(get_supabase)):
    """Login user."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return TokenResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            user=response.user.dict()
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase)
):
    """Get current authenticated user."""
    try:
        token = credentials.credentials
        user = supabase.auth.get_user(token)
        return {"user": user.user.dict()}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/signout")
async def signout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase)
):
    """Logout user."""
    try:
        token = credentials.credentials
        supabase.auth.admin.sign_out(token)
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))