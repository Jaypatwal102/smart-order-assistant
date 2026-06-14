from pydantic import BaseModel, EmailStr
import uuid
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    first_name: str | None
    last_name: str | None
    role: str
    created_at: datetime
    conversations: list[dict] = []

    class Config:
        from_attributes = True
