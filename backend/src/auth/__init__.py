"""Authentication and user management package.

This package encapsulates all functionality related to user
authentication, registration and profile retrieval.  To register the
user related routes with the main application you only need to
import and include the router defined in ``router.py``.  Business
logic and reusable helpers live in ``service.py`` while Pydantic
schemas used for request/response bodies are defined in
``schemas.py``.
"""

from .router import router  # noqa: F401
from .models import User  # noqa: F401
