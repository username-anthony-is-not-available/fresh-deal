from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import Settings
from app.core.db import init_db
from contextlib import asynccontextmanager
from app.api.endpoints import router as api_router
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


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            traces_sample_rate=1.0,
        )
    logging.getLogger(__name__).info("Application startup")
    init_db()
    yield
    # Shutdown


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


import re

def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom exception handler for rate limit exceeded errors.
    Calculates the Retry-After header from the exception detail.
    """
    response = JSONResponse(
        {"detail": f"Rate limit exceeded: {exc.detail}"}, status_code=429
    )

    # Try to parse the retry-after value from the exception detail
    retry_after = "60"  # Default value
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

# Restrict CORS to specific origins (frontend)
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:80",  # Production (if applicable)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(auth_endpoints.router, prefix="/auth", tags=["auth"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
