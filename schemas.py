from pydantic import BaseModel

from models import UserRole


class RegisterForm(BaseModel):
    email: str
    name: str
    password: str
    role: UserRole = UserRole.STAFF


class LoginForm(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole

    class Config:
        from_attributes = True