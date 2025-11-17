"""SQLAlchemy models for the authentication package.

This module defines the ``User`` model which stores user credentials
and relationships to other domain entities.  The relationship to
``NewsArticle`` is defined via the association table in
``src/models.py`` to avoid circular imports.
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from src.database import Base
from src.models import user_news_association_table


class User(Base):
    """User account table.

    Each user has a unique username and a hashed password.  The
    ``upvoted_news`` relationship links to news articles the user has
    upvoted via the association table defined in ``src/models.py``.  The
    corresponding back reference is defined in ``src/news/models.py``.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)

    # Relationship to NewsArticle defined by secondary association table.
    upvoted_news = relationship(
        "NewsArticle",
        secondary=user_news_association_table,
        back_populates="upvoted_by_users",
    )
