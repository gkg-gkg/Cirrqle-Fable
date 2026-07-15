"""Auth endpoints: create an account, sign in, and fetch the current user.

Signin optionally goes through an emailed 6-digit code (2FA), gated behind the
CIRQLE_LOGIN_2FA env flag (off by default so existing logins keep working).
There's also a real 'forgot password' flow (emailed reset link). All email is
best-effort via app.email (a no-op locally / in tests).
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from ..db import get_session
from ..email import send_login_code, send_password_reset
from ..models import (AuthOut, ForgotPasswordIn, LoginCode, PasswordChangeIn,
                      PasswordResetToken, ProfileUpdateIn, ResendCodeIn,
                      ResetPasswordIn, SigninIn, SigninOut, SignupIn, User,
                      UserOut, VerifyCodeIn)
from ..security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# 2FA / reset tuning.
CODE_TTL_MINUTES = 10
CODE_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 30
RESET_TTL_MINUTES = 30

# Base URL of the frontend, used to build the password-reset link in the email.
SITE_URL = os.environ.get("CIRQLE_SITE_URL", "https://gkg-gkg.github.io/Cirrqle-Fable").rstrip("/")


def _login_2fa_enabled() -> bool:
    """Read the flag at call time (not import) so tests/deploys can toggle it."""
    return os.environ.get("CIRQLE_LOGIN_2FA", "").strip().lower() in ("1", "true", "on", "yes")


def _generate_code() -> str:
    """A random, zero-padded 6-digit code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_token(token: str) -> str:
    """Deterministic hash for the high-entropy reset token (so we can look it up)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_login_code(user: User, session: Session) -> None:
    """Create + store a fresh login code for the user and email it."""
    code = _generate_code()
    session.add(LoginCode(
        user_id=user.id,
        code_hash=hash_password(code),
        expires_at=datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES),
    ))
    session.commit()
    send_login_code(user.email, code)


def _normalize_handle(raw: str) -> str:
    """Trim, drop a leading @, lowercase — matches the frontend's normalisation."""
    return raw.strip().lstrip("@").lower()


def _user_out(user: User) -> UserOut:
    return UserOut(
        firstName=user.first_name,
        lastName=user.last_name,
        email=user.email,
        instagramHandle=user.instagram_handle,
        createdAt=user.created_at,
    )


@router.post("/signup", response_model=AuthOut, status_code=201)
def signup(data: SignupIn, session: Session = Depends(get_session)):
    email = data.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if len(data.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")

    user = User(
        first_name=data.firstName.strip(),
        last_name=data.lastName.strip(),
        email=email,
        password_hash=hash_password(data.password),
        instagram_handle=_normalize_handle(data.instagramHandle),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthOut(token=create_token(user.id), user=_user_out(user))


@router.post("/signin", response_model=SigninOut)
def signin(data: SigninIn, session: Session = Depends(get_session)):
    """Verify email + password.

    With CIRQLE_LOGIN_2FA off (default) this returns the JWT straight away, just
    like before. With it on, no token is returned — instead a 6-digit code is
    emailed and the caller must finish via /auth/verify-code.
    """
    email = data.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    if _login_2fa_enabled():
        _issue_login_code(user, session)
        return SigninOut(codeRequired=True)

    return SigninOut(token=create_token(user.id), user=_user_out(user))


@router.post("/verify-code", response_model=AuthOut)
def verify_code(data: VerifyCodeIn, session: Session = Depends(get_session)):
    """Finish a 2FA sign-in: exchange the emailed code for a login token."""
    stale = HTTPException(status_code=400, detail="That code has expired. Request a new one.")
    email = data.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise stale

    row = session.exec(
        select(LoginCode)
        .where(LoginCode.user_id == user.id, LoginCode.consumed == False)  # noqa: E712
        .order_by(LoginCode.created_at.desc())
    ).first()
    if row is None or row.expires_at < datetime.utcnow():
        raise stale
    if row.attempts >= CODE_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new code.")

    # Count this try before checking, so a wrong guess always burns an attempt.
    row.attempts += 1
    session.add(row)
    session.commit()

    if not verify_password(data.code.strip(), row.code_hash):
        raise HTTPException(status_code=401, detail="Incorrect code. Please try again.")

    row.consumed = True
    session.add(row)
    session.commit()
    return AuthOut(token=create_token(user.id), user=_user_out(user))


@router.post("/resend-code", response_model=SigninOut)
def resend_code(data: ResendCodeIn, session: Session = Depends(get_session)):
    """Email a fresh 2FA code. Lightly rate-limited to stop rapid re-sends.

    Always reports success (never reveals whether the email has an account).
    """
    email = data.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is not None:
        latest = session.exec(
            select(LoginCode)
            .where(LoginCode.user_id == user.id)
            .order_by(LoginCode.created_at.desc())
        ).first()
        cutoff = datetime.utcnow() - timedelta(seconds=RESEND_COOLDOWN_SECONDS)
        if latest is not None and latest.created_at > cutoff:
            raise HTTPException(status_code=429, detail="Please wait a moment before requesting another code.")
        _issue_login_code(user, session)
    return SigninOut(codeRequired=True)


@router.post("/forgot-password", status_code=200)
def forgot_password(data: ForgotPasswordIn, session: Session = Depends(get_session)):
    """Email a password-reset link. Always 200 — never leaks whether the email
    has an account."""
    email = data.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is not None:
        token = secrets.token_urlsafe(32)
        session.add(PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.utcnow() + timedelta(minutes=RESET_TTL_MINUTES),
        ))
        session.commit()
        send_password_reset(user.email, f"{SITE_URL}/reset-password.html?token={token}")
    return {"ok": True}


@router.post("/reset-password", status_code=204)
def reset_password(data: ResetPasswordIn, session: Session = Depends(get_session)):
    """Set a new password from a valid, unexpired reset token."""
    if len(data.newPassword) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")

    row = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(data.token),
            PasswordResetToken.consumed == False,  # noqa: E712
        )
    ).first()
    if row is None or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user = session.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user.password_hash = hash_password(data.newPassword)
    row.consumed = True
    session.add(user)
    session.add(row)
    session.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    data: ProfileUpdateIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Let a logged-in user update their own profile: name, email, IG handle.

    PATCH semantics — only the fields present in the body are changed. Email
    must stay unique (it's the login identity), so we reject a clash with any
    other account.
    """
    if data.firstName is not None:
        first = data.firstName.strip()
        if not first:
            raise HTTPException(status_code=422, detail="First name can't be empty.")
        user.first_name = first

    if data.lastName is not None:
        last = data.lastName.strip()
        if not last:
            raise HTTPException(status_code=422, detail="Last name can't be empty.")
        user.last_name = last

    if data.email is not None:
        email = data.email.lower()
        clash = session.exec(select(User).where(User.email == email)).first()
        if clash is not None and clash.id != user.id:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        user.email = email

    if data.instagramHandle is not None:
        handle = _normalize_handle(data.instagramHandle)
        if not handle:
            raise HTTPException(status_code=422, detail="Instagram handle can't be empty.")
        user.instagram_handle = handle

    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_out(user)


@router.post("/me/password", status_code=204)
def change_password(
    data: PasswordChangeIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Change the signed-in user's password (verifies the current one first)."""
    if not verify_password(data.currentPassword, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(data.newPassword) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")
    user.password_hash = hash_password(data.newPassword)
    session.add(user)
    session.commit()
    return Response(status_code=204)
