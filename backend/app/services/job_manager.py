import asyncio
import json
import uuid
from typing import Any, Callable, Coroutine, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Job
from app.db.session import AsyncSessionLocal


class JobManager:
    """Asynchronous background job manager supporting Celery and in-process async workers."""

    async def create_job(
        self,
        db: AsyncSession,
        job_type: str,
        task_coro_fn: Optional[Callable[..., Coroutine]] = None,
        *args,
        **kwargs
    ) -> Job:
        job = Job(
            id=f"job_{uuid.uuid4().hex[:10]}",
            job_type=job_type,
            status="processing",
            progress=5
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        if task_coro_fn:
            # Spawn background async task
            asyncio.create_task(self._run_background(job.id, task_coro_fn, *args, **kwargs))

        return job

    async def _run_background(
        self,
        job_id: str,
        task_coro_fn: Callable[..., Coroutine],
        *args,
        **kwargs
    ):
        async with AsyncSessionLocal() as session:
            stmt = select(Job).where(Job.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if not job:
                return

            try:
                job.status = "processing"
                job.progress = 20
                await session.commit()

                async def update_progress(pct: int):
                    async with AsyncSessionLocal() as s:
                        r = await s.execute(select(Job).where(Job.id == job_id))
                        j = r.scalar_one_or_none()
                        if j:
                            j.progress = min(99, max(j.progress, pct))
                            await s.commit()

                result = await task_coro_fn(session, progress_callback=update_progress, *args, **kwargs)

                # Fetch fresh job instance
                res_fresh = await session.execute(select(Job).where(Job.id == job_id))
                job_fresh = res_fresh.scalar_one_or_none()
                if job_fresh:
                    job_fresh.status = "completed"
                    job_fresh.progress = 100
                    job_fresh.result_json = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                    await session.commit()

            except Exception as e:
                res_fresh = await session.execute(select(Job).where(Job.id == job_id))
                job_fresh = res_fresh.scalar_one_or_none()
                if job_fresh:
                    job_fresh.status = "failed"
                    job_fresh.error_message = str(e)
                    await session.commit()

    async def get_job(self, db: AsyncSession, job_id: str) -> Optional[Job]:
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


job_manager = JobManager()
