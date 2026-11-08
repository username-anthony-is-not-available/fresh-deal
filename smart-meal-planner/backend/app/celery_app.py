import os
from celery import Celery
from app.core.config import settings

is_eager = settings.CELERY_TASK_ALWAYS_EAGER or settings.USE_SQLITE_LOCAL or os.environ.get("USE_SQLITE_LOCAL", "").lower() in ("true", "1")

if is_eager:
    broker_url = "memory://"
    result_backend = "cache+memory://"
else:
    broker_url = os.environ.get("REDIS_URL", settings.REDIS_URL)
    result_backend = os.environ.get("REDIS_URL", settings.REDIS_URL)

celery_app = Celery(
    "smart_meal_planner",
    broker=broker_url,
    backend=result_backend,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=is_eager,
    task_eager_propagates=is_eager,
)

celery_app.set_default()
