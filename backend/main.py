import json
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.middleware.cors import CORSMiddleware
import itertools
from sqlalchemy import delete, insert, select, create_engine
from sqlalchemy.orm import Session, sessionmaker, relationship
from typing import List, Optional
import requests
from fastapi import APIRouter, HTTPException, Query, Depends, status, FastAPI
import os
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, AnyHttpUrl
from sqlalchemy import (Column, ForeignKey, Integer, String, Table, Text)
from sqlalchemy.ext.declarative import declarative_base
from urllib.parse import quote
from bs4 import BeautifulSoup
from openai import OpenAI

# --- Database & Models Setup ---

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
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Schemas ---

class UserAuthSchema(BaseModel):
    username: str
    password: str

class PromptRequest(BaseModel):
    prompt: str

class NewsSumaryRequestSchema(BaseModel):
    content: str

# --- Configuration ---

sentry_sdk.init(
    dsn="https://4001ffe917ccb261aa0e0c34026dc343@o4505702629834752.ingest.us.sentry.io/4507694792704000",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")
_id_counter = itertools.count(start=1000000)
OPENAI_API_KEY = "xxx"
JWT_SECRET = '1892dhianiandowqd0n'
JWT_ALGORITHM = "HS256"

# --- Service Classes ---

class OpenAIService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def get_relevance(self, title: str) -> str:
        m = [
            {
                "role": "system",
                "content": "你是一個關聯度評估機器人，請評估新聞標題是否與「民生用品的價格變化」相關，並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)",
            },
            {"role": "user", "content": f"{title}"},
        ]
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=m,
        )
        return completion.choices[0].message.content

    def get_summary(self, content: str) -> dict:
        m = [
            {
                "role": "system",
                "content": "你是一個新聞摘要生成機器人，請統Z新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
            },
            {"role": "user", "content": f"{content}"},
        ]
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=m,
        )
        result = completion.choices[0].message.content
        if result:
            result_json = json.loads(result)
            return {"summary": result_json.get("影響"), "reason": result_json.get("原因")}
        return {"summary": "", "reason": ""}


    def extract_keywords(self, prompt: str) -> str:
        m = [
            {
                "role": "system",
                "content": "你是一個關鍵字提取機器人，用戶將會輸入一段文字，表示其希望看見的新聞內容，請提取出用戶希望看見的關鍵字，請截取最重要的關鍵字即可，避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字，若有多個關鍵字，請以空格分隔)",
            },
            {"role": "user", "content": f"{prompt}"},
        ]
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=m,
        )
        return completion.choices[0].message.content

class NewsScraper:
    def __init__(self, db: Session, openai_service: OpenAIService):
        self.db = db
        self.openai_service = openai_service

    def get_news_list_from_api(self, search_term: str, is_initial: bool = False) -> List:
        all_news_data = []
        if is_initial:
            a = []
            for p in range(1, 10):
                p2 = {
                    "page": p,
                    "id": f"search:{quote(search_term)}",
                    "channelId": 2,
                    "type": "searchword",
                }
                response = requests.get("https://udn.com/api/more", params=p2)
                a.extend(response.json().get("lists", []))
            all_news_data = a
        else:
            p = {
                "page": 1,
                "id": f"search:{quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get("https://udn.com/api/more", params=p)
            all_news_data = response.json().get("lists", [])
        return all_news_data

    def scrape_article_details(self, url: str) -> Optional[dict]:
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_tag = soup.find("h1", class_="article-content__title")
            time_tag = soup.find("time", class_="article-content__time")
            content_section = soup.find("section", class_="article-content__editor")

            if not all([title_tag, time_tag, content_section]):
                return None

            title = title_tag.text
            time = time_tag.text
            paragraphs = [
                p.text
                for p in content_section.find_all("p")
                if p.text.strip() != "" and "▪" not in p.text
            ]
            
            return {
                "url": url,
                "title": title,
                "time": time,
                "content": paragraphs,
            }
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None

    def add_new_to_db(self, news_data: dict):
        existing_news = self.db.query(NewsArticle).filter_by(url=news_data["url"]).first()
        if existing_news:
            return
            
        session = SessionLocal()
        try:
            session.add(NewsArticle(
                url=news_data["url"],
                title=news_data["title"],
                time=news_data["time"],
                content=" ".join(news_data.get("content", [])),
                summary=news_data.get("summary", ""),
                reason=news_data.get("reason", ""),
            ))
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error adding news to DB: {e}")
        finally:
            session.close()

    def process_and_save_news(self, is_initial: bool = False):
        news_data = self.get_news_list_from_api("價格", is_initial=is_initial)
        for news in news_data:
            title = news.get("title")
            url = news.get("titleLink")
            if not title or not url:
                continue

            relevance = self.openai_service.get_relevance(title)
            if relevance == "high":
                detailed_news = self.scrape_article_details(url)
                if detailed_news:
                    content_str = " ".join(detailed_news["content"])
                    summary_data = self.openai_service.get_summary(content_str)
                    detailed_news.update(summary_data)
                    self.add_new_to_db(detailed_news)

    def search_news_by_prompt(self, prompt: str) -> List[dict]:
        keywords = self.openai_service.extract_keywords(prompt)
        news_items = self.get_news_list_from_api(keywords, is_initial=False)
        news_list = []
        
        for news in news_items:
            url = news.get("titleLink")
            if not url:
                continue
                
            detailed_news = self.scrape_article_details(url)
            if detailed_news:
                detailed_news["content"] = " ".join(detailed_news["content"])
                detailed_news["id"] = next(_id_counter)
                news_list.append(detailed_news)
                
        return sorted(news_list, key=lambda x: x["time"], reverse=True)


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        user = self.db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    def get_current_user_from_token(self, token: str) -> Optional[User]:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            user = self.db.query(User).filter(User.username == username).first()
            if user is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            return user
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    def register_user(self, user_auth: UserAuthSchema) -> User:
        existing_user = self.db.query(User).filter(User.username == user_auth.username).first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
        
        hashed_password = self.get_password_hash(user_auth.password)
        db_user = User(username=user_auth.username, hashed_password=hashed_password)
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

class NewsService:
    def __init__(self, db: Session):
        self.db = db

    def get_article_upvote_details(self, article_id: int, user_id: Optional[int]):
        cnt = (
            self.db.query(user_news_association_table)
            .filter_by(news_articles_id=article_id)
            .count()
        )
        voted = False
        if user_id:
            voted = (
                self.db.query(user_news_association_table)
                .filter_by(news_articles_id=article_id, user_id=user_id)
                .first()
                is not None
            )
        return cnt, voted

    def get_all_news(self, user_id: Optional[int] = None) -> List[dict]:
        news = self.db.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
        result = []
        for n in news:
            upvotes, upvoted = self.get_article_upvote_details(n.id, user_id, self.db)
            article_dict = n.__dict__
            article_dict.pop('_sa_instance_state', None)
            article_dict.update({"upvotes": upvotes, "is_upvoted": upvoted})
            result.append(article_dict)
        return result

    def toggle_upvote(self, article_id: int, user_id: int) -> str:
        existing_upvote = self.db.execute(
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
            self.db.execute(delete_stmt)
            message = "Upvote removed"
        else:
            insert_stmt = insert(user_news_association_table).values(
                news_articles_id=article_id, user_id=user_id
            )
            self.db.execute(insert_stmt)
            message = "Article upvoted"
        
        self.db.commit()
        return message

    def news_exists(self, article_id: int) -> bool:
        return self.db.query(NewsArticle).filter_by(id=article_id).first() is not None

class PriceService:
    def get_necessities_prices(self, category: Optional[str], commodity: Optional[str]):
        try:
            response = requests.get(
                "https://opendata.ey.gov.tw/api/ConsumerProtection/NecessitiesPrice",
                params={"CategoryName": category, "Name": commodity},
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"External API error: {e}")

# --- FastAPI Dependencies ---

def get_openai_service():
    return OpenAIService(api_key=OPENAI_API_KEY)

def get_auth_service(db: Session = Depends(get_db)):
    return AuthService(db)

def get_news_service(db: Session = Depends(get_db)):
    return NewsService(db)

def get_scraping_service(
    db: Session = Depends(get_db),
    openai: OpenAIService = Depends(get_openai_service)
):
    return NewsScraper(db, openai)

def get_price_service():
    return PriceService()

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    return auth_service.get_current_user_from_token(token)

# --- FastAPI App & Scheduler ---

app = FastAPI()
bgs = BackgroundScheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_scheduled_job():
    db = SessionLocal()
    openai = OpenAIService(api_key=OPENAI_API_KEY)
    scraper = NewsScraper(db, openai)
    try:
        scraper.process_and_save_news(is_initial=False)
    except Exception as e:
        print(f"Scheduled job failed: {e}")
    finally:
        db.close()

@app.on_event("startup")
def start_scheduler():
    db = SessionLocal()
    try:
        if db.query(NewsArticle).count() == 0:
            openai = OpenAIService(api_key=OPENAI_API_KEY)
            scraper = NewsScraper(db, openai)
            scraper.process_and_save_news(is_initial=True)
    except Exception as e:
        print(f"Initial job failed: {e}")
    finally:
        db.close()
    
    bgs.add_job(run_scheduled_job, "interval", minutes=100)
    bgs.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    bgs.shutdown()

# --- API Endpoints ---

@app.post("/api/v1/users/login")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
):
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = auth_service.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/users/register")
def create_user(
    user: UserAuthSchema, 
    auth_service: AuthService = Depends(get_auth_service)
):
    db_user = auth_service.register_user(user)
    return {"id": db_user.id, "username": db_user.username}

@app.get("/api/v1/users/me")
def read_users_me(user: User = Depends(get_current_user)):
    return {"username": user.username}

@app.get("/api/v1/news/news")
def read_news(news_service: NewsService = Depends(get_news_service)):
    return news_service.get_all_news(user_id=None)

@app.get("/api/v1/news/user_news")
def read_user_news(
    user: User = Depends(get_current_user),
    news_service: NewsService = Depends(get_news_service)
):
    return news_service.get_all_news(user_id=user.id)

@app.post("/api/v1/news/search_news")
async def search_news(
    request: PromptRequest, 
    scraper: NewsScraper = Depends(get_scraping_service)
):
    return scraper.search_news_by_prompt(request.prompt)

@app.post("/api/v1/news/news_summary")
async def news_summary(
    payload: NewsSumaryRequestSchema,
    user: User = Depends(get_current_user),
    openai: OpenAIService = Depends(get_openai_service)
):
    return openai.get_summary(payload.content)

@app.post("/api/v1/news/{id}/upvote")
def upvote_article(
    id: int,
    user: User = Depends(get_current_user),
    news_service: NewsService = Depends(get_news_service),
):
    message = news_service.toggle_upvote(id, user.id)
    return {"message": message}

@app.get("/api/v1/prices/necessities-price")
def get_necessities_prices(
    category: Optional[str] = Query(None), 
    commodity: Optional[str] = Query(None),
    price_service: PriceService = Depends(get_price_service)
):
    return price_service.get_necessities_prices(category, commodity)