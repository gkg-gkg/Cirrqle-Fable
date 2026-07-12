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


class Mention(SQLModel, table=True):
    """One Instagram post that tags the brand, owned by one user.

    PK is the Instagram post id (a post has a single owner, so it maps to one
    user). `user_id` links it back to its owner — the standard "one table per
    kind of user data, keyed by user_id" pattern.
    """
    id: str = Field(primary_key=True)                    # Instagram post id
    user_id: int = Field(index=True, foreign_key="user.id")
    url: Optional[str] = None
    display_url: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[str] = None
    owner_username: Optional[str] = None
    owner_full_name: Optional[str] = None
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


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


class ProfileUpdateIn(BaseModel):
    # Only fields the user is allowed to change. Optional -> PATCH semantics
    # (send just what you want to update).
    instagramHandle: Optional[str] = None


# ── What the API returns (never includes the password hash) ──
class UserOut(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    instagramHandle: str


class AuthOut(BaseModel):
    token: str
    user: UserOut


# ── Instagram feed (Phase 2) ──
# A trimmed post shape: only the fields the feed page renders, so we never leak
# the rest of the raw scrape to the browser.
class FeedPost(BaseModel):
    id: Optional[str] = None
    url: Optional[str] = None
    displayUrl: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[str] = None
    ownerUsername: Optional[str] = None
    ownerFullName: Optional[str] = None
    likesCount: Optional[int] = None
    commentsCount: Optional[int] = None


class FeedRefreshOut(BaseModel):
    posts: list[FeedPost]
    updated: Optional[datetime] = None   # None when the user has no stored posts yet
