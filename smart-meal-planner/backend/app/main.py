from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import init_db
from contextlib import asynccontextmanager
from app.api.endpoints import router as api_router
from app.core.logging_config import setup_logging
import logging
from prometheus_fastapi_instrumentator import Instrumentator
import sentry_sdk

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
    lifespan=lifespan
)

Instrumentator().instrument(app).expose(app)

# Restrict CORS to specific origins (frontend)
origins = [
    "http://localhost:5173", # Vite dev server
    "http://localhost:80",   # Production (if applicable)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Smart Meal Planner API is running"}
