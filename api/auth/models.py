from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Nom d'utilisateur ou email", example="admin")
    password: str = Field(..., description="Mot de passe", example="admin123")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class CreateAnalystRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr


class CreatedUserResponse(BaseModel):
    user: UserResponse
    generated_username: str
    generated_password: str