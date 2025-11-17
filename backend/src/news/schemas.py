"""Pydantic schemas for the news package.

Defines request and response models used by the news related
endpoints.  Splitting these schemas out from the router keeps the
route handlers clean and makes schema reuse straightforward.
"""

from pydantic import BaseModel
from typing import Optional


class SearchNewsRequest(BaseModel):
    """Request body for searching news articles based on a freeform prompt."""

    prompt: str


class NewsSummaryRequest(BaseModel):
    """Request body for summarizing a news article."""

    content: str


class NewsArticleOut(BaseModel):
    """Schema used when returning news articles to clients."""

    id: int
    url: str
    title: str
    time: str
    content: str
    summary: Optional[str] = None
    reason: Optional[str] = None
    upvotes: Optional[int] = None
    is_upvoted: Optional[bool] = None

    class Config:
        orm_mode = True
