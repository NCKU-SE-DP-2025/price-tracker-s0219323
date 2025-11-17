"""Business logic for user authentication and management.

This module encapsulates reusable functionality for verifying
passwords, hashing passwords, generating JWT access tokens and
retrieving users from the database.  Keeping these helpers in a
dedicated service module decouples them from the web layer, making
them easier to test and reuse elsewhere (for example in background
tasks or other services).
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.database import get_db
from .constants import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from .models import User


# Password hashing context.  See passlib documentation for details on
# available schemes.  ``deprecated="auto"`` means old hashes will be
# automatically updated when the password is verified.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme used to extract the JWT from incoming requests.  The
# ``tokenUrl`` must match the login endpoint defined in the router.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if ``plain_password`` matches ``hashed_password``."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using the configured context."""
    return pwd_context.hash(password)


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Return the first user with the given username or ``None``."""
    return db.query(User).filter(User.username == username).first()


def check_user_password_is_correct(db: Session, username: str, password: str) -> Optional[User]:
    """Validate a username/password combination.

    Returns the user instance on success or ``None`` on failure.
    """
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a JWT access token.

    ``data`` should contain any claims to be encoded into the token.  The
    ``sub`` claim is typically used to store the username.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user_token(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Resolve a JWT token into a user.

    This function is designed to be used as a dependency in FastAPI
    routes.  It will raise an ``HTTPException`` if the token is
    invalid or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    return user
