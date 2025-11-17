"""Constants used throughout the authentication subsystem.

Defining constants in one place prevents magic numbers and strings
from being scattered throughout the codebase.  Secrets should be
loaded from environment variables in a real application.  These
values are hard coded here for demonstration purposes and will need
to be replaced in production.
"""

# Secret key used for JWT token generation.  Replace with a strong
# random value in production.  Do not check real secrets into source
# control.
SECRET_KEY: str = "1892dhianiandowqd0n"

# Algorithm used for signing JWT tokens.  See `jose` documentation
# for other supported algorithms.
ALGORITHM: str = "HS256"

# Lifetime of access tokens in minutes.  Auth endpoints use this
# value to determine how long a generated token remains valid.
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
