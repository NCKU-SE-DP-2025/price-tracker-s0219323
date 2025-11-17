"""SQLAlchemy models for the news package.

Defines the ``NewsArticle`` ORM model which represents a news
article stored in the application database.  Relationships to the
``User`` model are declared via the association table in
``src/models.py``.
"""

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from src.database import Base
from src.models import user_news_association_table


class NewsArticle(Base):
    """Database model representing a news article."""

    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    time = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)

    # Relationship to users who have upvoted this article.  Defined as
    # back reference of the relationship defined on ``User``.
    upvoted_by_users = relationship(
        "User",
        secondary=user_news_association_table,
        back_populates="upvoted_news",
    )
