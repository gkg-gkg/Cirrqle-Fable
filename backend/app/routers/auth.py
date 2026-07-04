"""Auth endpoints: create an account, sign in, and fetch the current user."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import AuthOut, SigninIn, SignupIn, User, UserOut
from ..security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_handle(raw: str) -> str:
    """Trim, drop a leading @, lowercase — matches the frontend's normalisation."""
    return raw.strip().lstrip("@").lower()


def _user_out(user: User) -> UserOut:
    return UserOut(
        firstName=user.first_name,
        lastName=user.last_name,
        email=user.email,
        instagramHandle=user.instagram_handle,
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


@router.post("/signin", response_model=AuthOut)
def signin(data: SigninIn, session: Session = Depends(get_session)):
    email = data.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return AuthOut(token=create_token(user.id), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)
