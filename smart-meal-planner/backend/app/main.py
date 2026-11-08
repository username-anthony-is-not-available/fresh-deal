from app.celery_app import celery_app
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import Settings
from app.core.db import init_db
from contextlib import asynccontextmanager
from app.api.endpoints import router as api_router
from app.api import nutrition
from app.api import deals_export
from app.api import flyer_upload
from app.api import plan_export
from app.core.logging_config import setup_logging
import logging
from prometheus_fastapi_instrumentator import Instrumentator
import sentry_sdk
from app.api import auth_endpoints
from app.core.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scheduled_jobs import run_scheduled_scrape, run_pantry_expiration_check
from app.tasks import cleanup_old_data_task, send_daily_digests_task
import os
import re


settings = Settings()
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=1.0,
        )
    logging.getLogger(__name__).info("Application startup")
    init_db()

    # In-Process APScheduler for Local Runs
    cron_schedule_str = os.environ.get("REFRESH_CRON_SCHEDULE", "0 6 * * *")
    try:
        cron_parts = cron_schedule_str.split()
        if len(cron_parts) != 5:
            raise ValueError("CRON schedule must have 5 parts.")
        scheduler.add_job(
            run_scheduled_scrape,
            "cron",
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2],
            month=cron_parts[3],
            day_of_week=cron_parts[4],
        )
    except ValueError as e:
        logging.getLogger(__name__).warning(
            f"Invalid CRON schedule '{cron_schedule_str}', falling back to default '0 6 * * *'. Error: {e}"
        )
        scheduler.add_job(run_scheduled_scrape, "cron", hour=6, minute=0)

    # Weekly cleanup task
    scheduler.add_job(cleanup_old_data_task, "cron", day_of_week="sun", hour=0, minute=0)

    # Daily Email Digest
    scheduler.add_job(send_daily_digests_task, "cron", hour=8, minute=0)

    # In-Process Pantry Expiration Check (runs daily at 7 AM)
    scheduler.add_job(run_pantry_expiration_check, "cron", hour=7, minute=0)

    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown()


app = FastAPI(
    title="Smart Meal Planner API",
    description="API for managing meal plans, recipes, and grocery deals.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    response = JSONResponse(
        {"detail": f"Rate limit exceeded: {exc.detail}"}, status_code=429
    )

    retry_after = "60"
    if exc.detail:
        match = re.search(r"(\d+)\s*(second|minute|hour|day)", exc.detail)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "second":
                retry_after = str(amount)
            elif unit == "minute":
                retry_after = str(amount * 60)
            elif unit == "hour":
                retry_after = str(amount * 3600)
            elif unit == "day":
                retry_after = str(amount * 86400)

    response.headers["Retry-After"] = retry_after
    return response


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

Instrumentator().instrument(app).expose(app)

# Allow CORS for localhost and local LAN IPs (for mobile testing)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:80",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_endpoints.router, prefix="/auth", tags=["auth"])
app.include_router(nutrition.router, prefix="/api", tags=["nutrition"])
app.include_router(deals_export.router, prefix="/api", tags=["deals-export"])
app.include_router(flyer_upload.router, prefix="/api", tags=["flyer-upload"])
app.include_router(plan_export.router, prefix="/api", tags=["plan-export"])
app.include_router(api_router, prefix="/api", tags=["api"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
