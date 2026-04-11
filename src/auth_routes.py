from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from .auth import create_access_token, hash_password, verify_password
from .database import create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(body: RegisterRequest):
    if get_user_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    if len(body.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )

    user = create_user(body.email, hash_password(body.password), body.name)
    token = create_access_token({"sub": user["email"], "name": user["name"]})

    return AuthResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user["email"], "name": user["name"]})

    return AuthResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )
