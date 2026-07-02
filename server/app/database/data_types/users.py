import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.database.tables.users import UserRole

class UserBase(BaseModel):
    first_name: str
    last_name: str | None = None
    email: EmailStr
    role: UserRole | None = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    uid: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
