"""Prices domain package.

This package contains a simple wrapper around the Consumer Protection
open data API.  It provides an endpoint to fetch prices of
necessities.  Additional pricing related functionality can be added
here following the same pattern used for other domains.
"""

from .router import router  # noqa: F401
