"""Global configuration values for the application.

This module centralizes configuration values that are used across
multiple parts of the application.  Having a single location for
configuration helps reduce duplication and makes it easy to see what
can be tweaked without digging through business logic.  For secrets
and environment specific values you may wish to load from
environment variables rather than hard‐coding them here.
"""

from typing import List

# Origins allowed for CORS middleware.  When exposing your API to a
# frontend application running on another port or domain, add its
# origin to this list.
ALLOWED_ORIGINS: List[str] = ["http://localhost:8080"]
