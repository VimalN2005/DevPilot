import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.job_manager import job_manager

router = APIRouter(prefix="/jobs", tags=["Background AI Jobs"])


@router.get("/{job_id}")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Poll the status of an asynchronous background job.
    Returns status: queued | processing (progress 0-100%) | completed | failed.
    """
    job = await job_manager.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    parsed_result = None
    if job.result_json:
        try:
            parsed_result = json.loads(job.result_json)
        except Exception:
            parsed_result = job.result_json

    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "result": parsed_result,
        "error": job.error_message,
        "created_at": str(job.created_at),
        "updated_at": str(job.updated_at)
    }
