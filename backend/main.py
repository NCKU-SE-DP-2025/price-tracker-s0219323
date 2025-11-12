"""Application entry point.

This module creates the FastAPI application, configures middleware,
initialises the database, sets up the background scheduler and
registers routers from each domain.  It also initialises Sentry
monitoring if configured.

The structure follows the recommendations from FastAPI best practices
with a clear separation between configuration, domain specific code
and application composition.
"""

try:
    import sentry_sdk  # type: ignore
except ImportError:
    # Sentry is optional; if the package is not installed the application will still run
    sentry_sdk = None
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    # APScheduler is optional; if the package is not installed the
    # application will still run but periodic news fetching will be
    # disabled.  You can install ``apscheduler`` to enable the
    # scheduler.
    BackgroundScheduler = None  # type: ignore
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import ALLOWED_ORIGINS
from src.database import Base, engine
from src.auth import router as auth_router
from src.news import router as news_router
from src.prices import router as prices_router
from src.news.service import ensure_initial_news, schedule_fetch_news

# Initialise Sentry.  Replace the DSN with your own if you want to send
# error and performance data to Sentry.  Without a valid DSN the
# client will be inert.
if sentry_sdk:
    sentry_sdk.init(
        dsn="https://4001ffe917ccb261aa0e0c34026dc343@o4505702629834752.ingest.us.sentry.io/4507694792704000",
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# Create the FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure database tables are created
Base.metadata.create_all(bind=engine)

# Create a background scheduler for periodic tasks if APScheduler is available
scheduler = BackgroundScheduler() if BackgroundScheduler is not None else None


@app.on_event("startup")
def on_startup() -> None:
    """Application startup hook.

    Ensures the database has initial data and schedules periodic
    fetching of news articles.
    """
    # Seed the database if required
    ensure_initial_news()
    # Schedule periodic news fetching every 100 minutes
    # Start the scheduler only if the APScheduler library is available
    if scheduler is not None:
        scheduler.add_job(schedule_fetch_news, "interval", minutes=100)
        scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    """Application shutdown hook.

    Stops the background scheduler gracefully.
    """
    if scheduler is not None:
        scheduler.shutdown()


# Register routers with prefixes
app.include_router(auth_router, prefix="/api/v1/users")
app.include_router(news_router, prefix="/api/v1/news")
app.include_router(prices_router, prefix="/api/v1/prices")
