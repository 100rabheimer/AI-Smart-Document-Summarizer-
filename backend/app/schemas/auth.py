import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None


class UserRead(UserBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoogleAuthURLResponse(BaseModel):
    url: str
    state: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: Optional[UserRead] = None
