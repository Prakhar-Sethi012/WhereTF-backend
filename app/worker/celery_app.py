import os
from celery import Celery

# Grab the Redis URL from the environment variables defined in docker-compose.yml
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "wheretf_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker.tasks"]
)

# Standard configuration for JSON serialization
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)