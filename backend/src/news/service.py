"""Service layer for the news domain.

The functions defined here handle the heavy lifting of talking to
external services, parsing responses, interacting with the database
and preparing data for API responses.  By isolating the business
logic from the API layer we make it easier to test and maintain.
"""

import itertools
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from src.database import SessionLocal, session_scope
from src.models import user_news_association_table
from .models import NewsArticle

# Private counter for assigning temporary IDs when returning search
# results that are not yet persisted in the database.  Starting at a
# high value avoids collisions with auto incremented IDs in the DB.
_id_counter = itertools.count(start=1000000)


def add_new(db: Session, news_data: Dict[str, Any]) -> NewsArticle:
    """Persist a new ``NewsArticle`` in the database.

    The input ``news_data`` should contain keys for ``url``, ``title``,
    ``time``, ``content``, ``summary`` and ``reason``.  The caller is
    responsible for ensuring that these keys exist.
    """
    article = NewsArticle(
        url=news_data["url"],
        title=news_data["title"],
        time=news_data["time"],
        content=news_data["content"],
        summary=news_data["summary"],
        reason=news_data["reason"],
    )
    db.add(article)
    db.commit()
    return article


def get_new_info(search_term: str, is_initial: bool = False) -> List[Any]:
    """Query the UDN news API and return raw article metadata.

    If ``is_initial`` is True the function will fetch multiple pages of
    results to seed the database; otherwise only the first page is
    fetched.  The returned items are JSON structures returned from
    UDN.
    """
    all_news_data: List[Any] = []
    if is_initial:
        pages: List[Any] = []
        for p in range(1, 10):
            p2 = {
                "page": p,
                "id": f"search:{requests.utils.quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get("https://udn.com/api/more", params=p2)
            pages.append(response.json().get("lists", []))
        for lst in pages:
            all_news_data.append(lst)
    else:
        params = {
            "page": 1,
            "id": f"search:{requests.utils.quote(search_term)}",
            "channelId": 2,
            "type": "searchword",
        }
        response = requests.get("https://udn.com/api/more", params=params)
        all_news_data = response.json().get("lists", [])
    return all_news_data


def fetch_and_store_news(is_initial: bool = False) -> None:
    """Fetch news articles and store relevant ones in the database.

    This function queries the UDN API with a default search term and
    then uses OpenAI to classify article relevance and summarise the
    content.  Only articles deemed highly relevant are stored.  It is
    intended to be run periodically as part of a scheduler.
    """
    news_data = get_new_info("價格", is_initial=is_initial)
    # Flatten the list when initial seeding to handle the nested lists
    if is_initial:
        flattened: List[Any] = []
        for sublist in news_data:
            flattened.extend(sublist)
        news_data = flattened
    with session_scope() as db:
        for news in news_data:
            title = news.get("title")
            # Use OpenAI to rate relevance
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "你是一個關聯度評估機器人，請評估新聞標題是否與「民生用品的價格變化」相關，並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)",
                    },
                    {"role": "user", "content": f"{title}"},
                ]
                ai = OpenAI(api_key="xxx").chat.completions.create(
                    model="gpt-3.5-turbo", messages=messages
                )
                relevance = ai.choices[0].message.content
            except Exception:
                # If the AI call fails, default to medium to avoid unnecessary filtering
                relevance = "medium"
            if relevance != "high":
                continue
            # Parse the article details
            try:
                response = requests.get(news["titleLink"])
                soup = BeautifulSoup(response.text, "html.parser")
                detailed_title = soup.find("h1", class_="article-content__title").text
                time = soup.find("time", class_="article-content__time").text
                content_section = soup.find("section", class_="article-content__editor")
                paragraphs = [
                    p.text
                    for p in content_section.find_all("p")
                    if p.text.strip() != "" and "▪" not in p.text
                ]
                detailed_news: Dict[str, Any] = {
                    "url": news["titleLink"],
                    "title": detailed_title,
                    "time": time,
                    "content": " ".join(paragraphs),
                }
            except Exception:
                # Skip this news item if parsing fails
                continue
            # Summarize the news using OpenAI
            try:
                messages = [
                    {
                        "role": "system",
                        "content": "你是一個新聞摘要生成機器人，請統整新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
                    },
                    {"role": "user", "content": detailed_news["content"]},
                ]
                completion = OpenAI(api_key="xxx").chat.completions.create(
                    model="gpt-3.5-turbo", messages=messages
                )
                result = completion.choices[0].message.content
                result_json = json.loads(result)
                detailed_news["summary"] = result_json.get("影響", "")
                detailed_news["reason"] = result_json.get("原因", "")
            except Exception:
                # If summarisation fails, store without summary/reason
                detailed_news["summary"] = ""
                detailed_news["reason"] = ""
            # Persist to DB
            add_new(db, detailed_news)


def ensure_initial_news() -> None:
    """Ensure the database has at least one news article.

    Called on application startup.  If no articles exist in the
    database this will trigger a bulk fetch and store of initial
    articles.
    """
    with session_scope() as db:
        if db.query(NewsArticle).count() == 0:
            fetch_and_store_news(is_initial=True)


def schedule_fetch_news() -> None:
    """Wrapper for the scheduler to periodically fetch news."""
    fetch_and_store_news(is_initial=False)


def get_article_upvote_details(article_id: int, uid: Optional[int], db: Session) -> Tuple[int, bool]:
    """Return the number of upvotes and whether the given user has upvoted.

    :param article_id: ID of the article
    :param uid: ID of the user (may be None)
    :param db: Active database session
    :return: A tuple ``(upvotes, is_upvoted)``
    """
    cnt = db.query(user_news_association_table).filter_by(news_articles_id=article_id).count()
    voted = False
    if uid:
        voted = (
            db.query(user_news_association_table)
            .filter_by(news_articles_id=article_id, user_id=uid)
            .first()
            is not None
        )
    return cnt, voted


def toggle_upvote(n_id: int, u_id: int, db: Session) -> str:
    """Toggle an upvote on a news article for a user.

    If the user has already upvoted the article the upvote is removed,
    otherwise a new upvote is recorded.

    :param n_id: ID of the news article
    :param u_id: ID of the user performing the action
    :param db: Active database session
    :return: A message describing the outcome
    """
    # Check if an upvote already exists
    existing_upvote = db.execute(
        select(user_news_association_table).where(
            user_news_association_table.c.news_articles_id == n_id,
            user_news_association_table.c.user_id == u_id,
        )
    ).scalar()
    if existing_upvote:
        delete_stmt = delete(user_news_association_table).where(
            user_news_association_table.c.news_articles_id == n_id,
            user_news_association_table.c.user_id == u_id,
        )
        db.execute(delete_stmt)
        db.commit()
        return "Upvote removed"
    else:
        insert_stmt = insert(user_news_association_table).values(
            news_articles_id=n_id, user_id=u_id
        )
        db.execute(insert_stmt)
        db.commit()
        return "Article upvoted"


async def search_news(prompt: str) -> List[Dict[str, Any]]:
    """Search for news articles based on a user prompt.

    Uses OpenAI to extract keywords from the prompt before querying
    UDN.  Returned articles are parsed and given temporary IDs.
    """
    news_list: List[Dict[str, Any]] = []
    # Extract keywords via OpenAI
    messages = [
        {
            "role": "system",
            "content": "你是一個關鍵字提取機器人，用戶將會輸入一段文字，表示其希望看見的新聞內容，請提取出用戶希望看見的關鍵字，請截取最重要的關鍵字即可，避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字，若有多個關鍵字，請以空格分隔)",
        },
        {"role": "user", "content": prompt},
    ]
    try:
        completion = OpenAI(api_key="xxx").chat.completions.create(
            model="gpt-3.5-turbo", messages=messages
        )
        keywords = completion.choices[0].message.content
    except Exception:
        # Fallback: use the original prompt directly as keywords
        keywords = prompt
    # Query UDN API for news articles
    news_items = get_new_info(keywords, is_initial=False)
    for news in news_items:
        try:
            response = requests.get(news["titleLink"])
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.find("h1", class_="article-content__title").text
            time = soup.find("time", class_="article-content__time").text
            content_section = soup.find("section", class_="article-content__editor")
            paragraphs = [
                p.text
                for p in content_section.find_all("p")
                if p.text.strip() != "" and "▪" not in p.text
            ]
            detailed_news: Dict[str, Any] = {
                "url": news["titleLink"],
                "title": title,
                "time": time,
                "content": " ".join(paragraphs),
            }
            detailed_news["id"] = next(_id_counter)
            news_list.append(detailed_news)
        except Exception:
            # Skip any news article that fails to parse
            continue
    # Sort by time in descending order.  The time field is a string,
    # usually formatted as something like "2023-08-01 12:34", which
    # sorts correctly as a string.  If not, convert to datetime first.
    news_list.sort(key=lambda x: x.get("time", ""), reverse=True)
    return news_list


async def summarize_content(content: str) -> Dict[str, str]:
    """Generate a summary and reason for the given news content.

    Uses OpenAI to produce a JSON with ``影響`` and ``原因`` keys.
    Returns a dictionary with English keys ``summary`` and ``reason``.
    """
    messages = [
        {
            "role": "system",
            "content": "你是一個新聞摘要生成機器人，請統整新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
        },
        {"role": "user", "content": content},
    ]
    try:
        completion = OpenAI(api_key="xxx").chat.completions.create(
            model="gpt-3.5-turbo", messages=messages
        )
        result = completion.choices[0].message.content
        result_json = json.loads(result)
        return {
            "summary": result_json.get("影響", ""),
            "reason": result_json.get("原因", ""),
        }
    except Exception:
        return {"summary": "", "reason": ""}
