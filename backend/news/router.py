"""API routes for interacting with news articles.

Endpoints in this router allow clients to list all news articles,
retrieve news specific to the current user, perform ad hoc searches,
generate summaries and toggle upvotes on articles.  The router is
included under the ``/api/v1/news`` prefix by the main application.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.dependencies import get_current_user
from .models import NewsArticle
from .schemas import NewsArticleOut, SearchNewsRequest, NewsSummaryRequest
from .service import (
    get_article_upvote_details,
    toggle_upvote,
    search_news as service_search_news,
    summarize_content,
)


router = APIRouter()


@router.get("/news", response_model=List[NewsArticleOut])
def read_news(db: Session = Depends(get_db)):
    """Return all news articles sorted by time descending.

    For each article the total number of upvotes and whether the
    current (anonymous) user has upvoted it is included.  Because
    anonymous users cannot upvote, the ``is_upvoted`` flag will
    always be False in this endpoint.
    """
    articles = db.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
    result = []
    for article in articles:
        upvotes, upvoted = get_article_upvote_details(article.id, None, db)
        # Use the article's __dict__ to get model fields; copy to avoid
        # modifying internal state.
        data = {
            "id": article.id,
            "url": article.url,
            "title": article.title,
            "time": article.time,
            "content": article.content,
            "summary": article.summary,
            "reason": article.reason,
            "upvotes": upvotes,
            "is_upvoted": upvoted,
        }
        result.append(data)
    return result


@router.get("/user_news", response_model=List[NewsArticleOut])
def read_user_news(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """Return all news articles with user specific upvote information.

    Uses ``current_user`` dependency to determine whether each article
    has been upvoted by the logged in user.
    """
    articles = db.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
    result = []
    for article in articles:
        upvotes, upvoted = get_article_upvote_details(article.id, current_user.id, db)
        data = {
            "id": article.id,
            "url": article.url,
            "title": article.title,
            "time": article.time,
            "content": article.content,
            "summary": article.summary,
            "reason": article.reason,
            "upvotes": upvotes,
            "is_upvoted": upvoted,
        }
        result.append(data)
    return result


@router.post("/search_news")
async def search_news_endpoint(request: SearchNewsRequest):
    """Search for news articles given a freeform prompt.

    Returns a list of news article dictionaries with temporary IDs.
    """
    return await service_search_news(request.prompt)


@router.post("/news_summary")
async def news_summary_endpoint(
    payload: NewsSummaryRequest, current_user=Depends(get_current_user)
):
    """Generate a summary and reason for a provided news article content.

    Requires authentication because summarisation consumes API quota and
    is considered a personalised operation.
    """
    return await summarize_content(payload.content)


@router.post("/{id}/upvote")
def upvote_article(
    id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """Toggle an upvote for the current user on the specified article."""
    message = toggle_upvote(id, current_user.id, db)
    return {"message": message}
