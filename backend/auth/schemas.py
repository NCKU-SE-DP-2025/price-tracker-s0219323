"""Pydantic schemas for the authentication package.

Schemas define the shape of request and response bodies for the
authentication endpoints.  They help document the API and provide
validation of incoming data.
"""

from pydantic import BaseModel


class UserCreate(BaseModel):
    """Schema for user registration requests."""

    username: str
    password: str


class UserLoginResponse(BaseModel):
    """Schema for login responses.

    Contains the access token and its type.  Additional fields
    (such as refresh tokens) could be added here in the future.
    """

    access_token: str
    token_type: str


class UserOut(BaseModel):
    """Schema used when returning user information to clients."""

    id: int
    username: str

    class Config:
        orm_mode = True
