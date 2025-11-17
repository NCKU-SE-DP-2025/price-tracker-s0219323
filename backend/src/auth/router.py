"""API routes related to user authentication and management.

This router defines endpoints for registering new users, logging in
existing users and retrieving the authenticated user's profile.
Routes are included into the main application with the prefix
``/api/v1/users`` in ``src/main.py``.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.database import get_db
from .schemas import UserCreate, UserLoginResponse, UserOut
from .service import (
    check_user_password_is_correct,
    create_access_token,
    get_password_hash,
)
from .dependencies import get_current_user
from .models import User


router = APIRouter()


@router.post("/login", response_model=UserLoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Authenticate a user and return a JWT access token.

    Accepts credentials via an ``OAuth2PasswordRequestForm`` as
    required by FastAPI's OAuth2 support.
    """
    user = check_user_password_is_correct(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password",
        )
    access_token = create_access_token(data={"sub": user.username}, expires_delta=timedelta(minutes=30))
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserOut)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account.

    A hashed password is generated before storing the user in the
    database.  Duplicate usernames will cause an integrity error
    raised by SQLAlchemy, which could be caught and transformed into a
    more user friendly response in the future.
    """
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/me", response_model=dict)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's public profile."""
    return {"username": current_user.username}
