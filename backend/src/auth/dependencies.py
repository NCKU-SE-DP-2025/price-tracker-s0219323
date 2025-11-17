"""Reusable dependencies for authentication.

This module provides dependency functions that can be injected into
FastAPI route handlers.  Using dependencies keeps route functions
clean and allows common patterns to be shared across the codebase.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from src.database import get_db
from .service import authenticate_user_token


def get_current_user(user=Depends(authenticate_user_token)):
    """Return the current authenticated user.

    This simply proxies through to the ``authenticate_user_token``
    function defined in the service module.  Keeping the dependency
    defined here avoids having to import FastAPI dependencies in the
    service layer and provides a clear place to expand future user
    retrieval logic.
    """
    return user
