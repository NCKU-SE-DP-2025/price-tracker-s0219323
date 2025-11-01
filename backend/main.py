import json
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.middleware.cors import CORSMiddleware
import itertools
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Optional
import requests
from fastapi import APIRouter, HTTPException, Query, Depends, status, FastAPI
import os
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from pydantic import BaseModel, Field, AnyHttpUrl
from sqlalchemy import (Column, ForeignKey, Integer, String, Table, Text,
                        create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

user_news_association_table = Table(
    "user_news_upvotes",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column(
        "news_articles_id", Integer, ForeignKey("news_articles.id"), primary_key=True
    ),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    upvoted_news = relationship(
        "NewsArticle",
        secondary=user_news_association_table,
        back_populates="upvoted_by_users",
    )

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    time = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    upvoted_by_users = relationship(
        "User", secondary=user_news_association_table, back_populates="upvoted_news"
    )

engine = create_engine("sqlite:///news_database.db", echo=True)

Base.metadata.create_all(engine)

SessionFactory = sessionmaker(bind=engine)

sentry_sdk.init(
    dsn="https://4001ffe917ccb261aa0e0c34026dc343@o4505702629834752.ingest.us.sentry.io/4507694792704000",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

app = FastAPI()
scheduler = BackgroundScheduler()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from openai import OpenAI

from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

def add_article_to_db(news_data):
    session = Session()
    session.add(NewsArticle(
        url=news_data["url"],
        title=news_data["title"],
        time=news_data["time"],
        content=" ".join(news_data["content"]),
        summary=news_data["summary"],
        reason=news_data["reason"],
    ))
    session.commit()
    session.close()

def fetch_news_data(search_term, is_initial=False):
    all_news_data = []
    if is_initial:
        articles_list = []
        for page in range(1, 10):
            page_params = {
                "page": page,
                "id": f"search:{quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get("https://udn.com/api/more", params=page_params)
            articles_list.append(response.json()["lists"])
        for news_page in articles_list:
            all_news_data.append(news_page)
    else:
        params = {
            "page": 1,
            "id": f"search:{quote(search_term)}",
            "channelId": 2,
            "type": "searchword",
        }
        response = requests.get("https://udn.com/api/more", params=params)
        all_news_data = response.json()["lists"]
    return all_news_data

def fetch_filtered_news(is_initial=False):
    news_data = fetch_news_data("價格", is_initial=is_initial)
    for news in news_data:
        title = news["title"]
        messages = [
            {
                "role": "system",
                "content": "你是一個關聯度評估機器人，請評估新聞標題是否與「民生用品的價格變化」相關，並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)",
            },
            {"role": "user", "content": f"{title}"},
        ]
        ai_response = OpenAI(api_key="xxx").chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        relevance = ai_response.choices[0].message.content
        if relevance == "high":
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
            detailed_news = {
                "url": news["titleLink"],
                "title": title,
                "time": time,
                "content": paragraphs,
            }
            messages = [
                {
                    "role": "system",
                    "content": "你是一個新聞摘要生成機器人，請統整新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
                },
                {"role": "user", "content": " ".join(detailed_news["content"])},
            ]

            completion = OpenAI(api_key="xxx").chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )
            parsed_result = json.loads(completion.choices[0].message.content)
            detailed_news["summary"] = parsed_result["影響"]
            detailed_news["reason"] = parsed_result["原因"]
            add_article_to_db(detailed_news)

@app.on_event("startup")
def start_scheduler():
    db_session = SessionLocal()
    if db_session.query(NewsArticle).count() == 0:
        fetch_filtered_news()
    db_session.close()
    scheduler.add_job(fetch_filtered_news, "interval", minutes=100)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")

def get_db_session():
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def validate_user_credentials(db_session, username, password):
    user = db_session.query(User).filter(User.username == username).first()
    if not verify_password(password, user.hashed_password):
        return False
    return user

def decode_user_token(
    token=Depends(oauth2_scheme),
    db_session=Depends(get_db_session)
):
    payload = jwt.decode(token, '1892dhianiandowqd0n', algorithms=["HS256"])
    return db_session.query(User).filter(User.username == payload.get("sub")).first()

def create_jwt_token(data, expires_delta=None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, '1892dhianiandowqd0n', algorithm="HS256")
    return encoded_jwt

@app.post("/api/v1/users/login")
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(), db_session: Session = Depends(get_db_session)
):
    user = validate_user_credentials(db_session, form_data.username, form_data.password)
    access_token = create_jwt_token(
        data={"sub": str(user.username)}, expires_delta=timedelta(minutes=30)
    )
    return {"access_token": access_token, "token_type": "bearer"}

class UserAuthSchema(BaseModel):
    username: str
    password: str

@app.post("/api/v1/users/register")
def create_user(user: UserAuthSchema, db_session: Session = Depends(get_db_session)):
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)
    return db_user

@app.get("/api/v1/users/me")
def read_users_me(current_user=Depends(decode_user_token)):
    return {"username": current_user.username}

article_id_counter = itertools.count(start=1000000)

def get_upvote_info(article_id, user_id, db_session):
    count = (
        db_session.query(user_news_association_table)
        .filter_by(news_articles_id=article_id)
        .count()
    )
    voted = False
    if user_id:
        voted = (
            db_session.query(user_news_association_table)
            .filter_by(news_articles_id=article_id, user_id=user_id)
            .first()
            is not None
        )
    return count, voted

@app.get("/api/v1/news/news")
def read_news(db_session=Depends(get_db_session)):
    news = db_session.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
    result = []
    for article in news:
        upvotes, upvoted = get_upvote_info(article.id, None, db_session)
        result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
    return result

@app.get("/api/v1/news/user_news")
def read_user_news(
        db_session=Depends(get_db_session),
        current_user=Depends(decode_user_token)
):
    news = db_session.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
    result = []
    for article in news:
        upvotes, upvoted = get_upvote_info(article.id, current_user.id, db_session)
        result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
    return result

class KeywordPromptRequest(BaseModel):
    prompt: str

@app.post("/api/v1/news/search_news")
async def search_news(request: KeywordPromptRequest):
    prompt = request.prompt
    news_list = []
    messages = [
        {
            "role": "system",
            "content": "你是一個關鍵字提取機器人，用戶將會輸入一段文字，表示其希望看見的新聞內容，請提取出用戶希望看見的關鍵字，請截取最重要的關鍵字即可，避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字，若有多個關鍵字，請以空格分隔)",
        },
        {"role": "user", "content": f"{prompt}"},
    ]

    completion = OpenAI(api_key="xxx").chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    keywords = completion.choices[0].message.content
    news_items = fetch_news_data(keywords, is_initial=False)
    for news in news_items:
        try:
            response = requests.get(news["titleLink"])
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.find("h1", class_="article-content__title").text
            time = soup.find("time", class_="article-content__time").text
            content_section = soup.find("section", class_="article-content__editor")

            paragraphs = [
                paragraph.text
                for paragraph in content_section.find_all("p")
                if paragraph.text.strip() != "" and "▪" not in paragraph.text
            ]

            detailed_news = {
                "url": news["titleLink"],
                "title": title,
                "time": time,
                "content": " ".join(paragraphs),
                "id": next(article_id_counter),
            }
            news_list.append(detailed_news)
        except Exception as e:
            print(e)
    return sorted(news_list, key=lambda x: x["time"], reverse=True)

class NewsSummaryRequest(BaseModel):
    content: str

@app.post("/api/v1/news/news_summary")
async def news_summary(payload: NewsSummaryRequest, current_user=Depends(decode_user_token)):
    response = {}
    messages = [
        {
            "role": "system",
            "content": "你是一個新聞摘要生成機器人，請統整新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
        },
        {"role": "user", "content": f"{payload.content}"},
    ]

    completion = OpenAI(api_key="xxx").chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    parsed_result = completion.choices[0].message.content
    if parsed_result:
        parsed_result = json.loads(parsed_result)
        response["summary"] = parsed_result["影響"]
        response["reason"] = parsed_result["原因"]
    return response

@app.post("/api/v1/news/{article_id}/upvote")
def upvote_article(
        article_id,
        db_session=Depends(get_db_session),
        current_user=Depends(decode_user_token),
):
    message = toggle_upvote(article_id, current_user.id, db_session)
    return {"message": message}

def toggle_upvote(article_id, user_id, db_session):
    existing_upvote = db_session.execute(
        select(user_news_association_table).where(
            user_news_association_table.c.news_articles_id == article_id,
            user_news_association_table.c.user_id == user_id,
        )
    ).scalar()

    if existing_upvote:
        delete_stmt = delete(user_news_association_table).where(
            user_news_association_table.c.news_articles_id == article_id,
            user_news_association_table.c.user_id == user_id,
        )
        db_session.execute(delete_stmt)
        db_session.commit()
        return "Upvote removed"
    else:
        insert_stmt = insert(user_news_association_table).values(
            news_articles_id=article_id, user_id=user_id
        )
        db_session.execute(insert_stmt)
        db_session.commit()
        return "Article upvoted"

def news_exists(article_id, db_session: Session):
    return db_session.query(NewsArticle).filter_by(id=article_id).first() is not None

@app.get("/api/v1/prices/necessities-price")
def get_necessities_prices(category=Query(None), commodity=Query(None)):
    return requests.get(
        "https://opendata.ey.gov.tw/api/ConsumerProtection/NecessitiesPrice",
        params={"CategoryName": category, "Name": commodity},
    ).json()
