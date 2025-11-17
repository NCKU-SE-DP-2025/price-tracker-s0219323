"""Database setup and session management.

This module defines the SQLAlchemy engine, session factory and base
class for declarative models.  It also exposes a ``get_db``
dependency which can be used in FastAPI routes and services to access
the database in a scoped manner.  All models across the project
should inherit from ``Base`` defined here.
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default to a local SQLite database if no environment variable is set.  You
# can override this by defining DATABASE_URL in your environment.
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///news_database.db")

# The SQLAlchemy engine is responsible for managing connections to the
# database.  Setting echo=True will log SQL statements which can be
# useful during development but should typically be disabled in
# production.
engine = create_engine(DATABASE_URL, echo=True)

# SessionLocal is a factory that can be used to create new session
# objects.  A session represents a database conversation and should
# normally be created and closed in a scoped manner, for example via
# dependencies in FastAPI.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the declarative base class that all ORM models must inherit from.
Base = declarative_base()


def get_db() -> Generator:
    """Yield a new SQLAlchemy session for use in a FastAPI dependency.

    The session is created using ``SessionLocal`` and closed after the
    request is handled.  This ensures that connections are cleaned up
    correctly after each request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator:
    """Provide a transactional scope for interacting with the database.

    This helper can be used in contexts where a dependency injection
    pattern isn’t suitable, such as background tasks or services that
    manage their own transactions.  Usage example::

        with session_scope() as db:
            db.add(some_model_instance)
            db.commit()

    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
