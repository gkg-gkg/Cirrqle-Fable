"""Database tables and the request/response shapes for the API.

`User` (table=True) is a real database table. The other classes are just the
JSON shapes we accept and return — kept separate so we never leak the password
hash to the browser.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    email: str = Field(index=True, unique=True)
    password_hash: str
    instagram_handle: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── What the browser sends ──
class SignupIn(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    password: str
    instagramHandle: str


class SigninIn(BaseModel):
    email: EmailStr
    password: str


# ── What the API returns (never includes the password hash) ──
class UserOut(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    instagramHandle: str


class AuthOut(BaseModel):
    token: str
    user: UserOut
