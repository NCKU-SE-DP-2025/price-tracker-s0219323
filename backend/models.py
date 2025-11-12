"""Shared models and tables.

While most domain specific models live inside their respective
subpackages (see ``src/auth/models.py`` and ``src/news/models.py``),
some tables need to be defined at a global level so they can be
referenced across domains without causing circular imports.  This
module contains such shared definitions.  In particular, the
``user_news_association_table`` maps users to news articles they have
upvoted.
"""

from sqlalchemy import Table, Column, Integer, ForeignKey

from .database import Base


# Association table linking users to the news articles they have upvoted.
# Both columns form a composite primary key to prevent duplicate
# associations.
user_news_association_table = Table(
    "user_news_upvotes",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column(
        "news_articles_id", Integer, ForeignKey("news_articles.id"), primary_key=True
    ),
)
