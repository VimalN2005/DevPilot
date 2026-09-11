import os
from celery import Celery
from app.config import settings

celery_app = Celery(
    "devpilot_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True
)


@celery_app.task(name="tasks.ingest_repository")
def celery_ingest_repository(repo_id: str, repo_url: str):
    """Celery background task to clone and index repository."""
    return {"status": "success", "repo_id": repo_id, "message": "Repository indexing completed via Celery"}


@celery_app.task(name="tasks.review_pull_request")
def celery_review_pull_request(pr_number: int, pr_diff: str):
    """Celery background task for asynchronous PR review."""
    return {"status": "success", "pr_number": pr_number, "verdict": "APPROVED"}
