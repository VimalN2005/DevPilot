from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.rbac import UserRole, require_role
from app.db.models import CodeChunk, CodeFile, Repository
from app.db.session import get_db
from app.services.github_service import github_service
from app.services.job_manager import job_manager

router = APIRouter(prefix="/repos", tags=["Repository Intelligence"])


class ConnectRepoRequest(BaseModel):
    name: str
    clone_url: Optional[str] = None
    local_path: Optional[str] = None
    branch: Optional[str] = "main"


class RepoResponse(BaseModel):
    id: str
    name: str
    owner: str
    clone_url: Optional[str]
    local_path: Optional[str]
    branch: str
    status: str
    total_files: int
    total_chunks: int


@router.post("/connect", status_code=status.HTTP_202_ACCEPTED)
async def connect_repository(
    req: ConnectRepoRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Connect a GitHub repository or local directory.
    Immediately responds with job_id and begins async ingestion.
    """
    # Create repository entry
    repo = Repository(
        name=req.name,
        clone_url=req.clone_url,
        local_path=req.local_path or str(settings.BASE_DIR),
        branch=req.branch or "main",
        status="indexing"
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    # Coroutine for background worker
    async def run_ingestion_task(session: AsyncSession, progress_callback=None):
        return await github_service.clone_and_ingest(session, repo, progress_callback)

    # Spawn background job
    job = await job_manager.create_job(
        db=db,
        job_type="repository_ingestion",
        task_coro_fn=run_ingestion_task
    )

    return {
        "message": "Repository connection initiated. Ingestion running in background.",
        "repo_id": repo.id,
        "job_id": job.id,
        "status": "processing"
    }


@router.get("", response_model=List[RepoResponse])
async def list_repositories(db: AsyncSession = Depends(get_db)):
    stmt = select(Repository).order_by(Repository.created_at.desc())
    res = await db.execute(stmt)
    repos = res.scalars().all()
    return [
        RepoResponse(
            id=r.id,
            name=r.name,
            owner=r.owner,
            clone_url=r.clone_url,
            local_path=r.local_path,
            branch=r.branch,
            status=r.status,
            total_files=r.total_files,
            total_chunks=r.total_chunks
        )
        for r in repos
    ]


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repository(repo_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Repository).where(Repository.id == repo_id)
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return RepoResponse(
        id=repo.id,
        name=repo.name,
        owner=repo.owner,
        clone_url=repo.clone_url,
        local_path=repo.local_path,
        branch=repo.branch,
        status=repo.status,
        total_files=repo.total_files,
        total_chunks=repo.total_chunks
    )


@router.get("/{repo_id}/files")
async def get_repository_files(repo_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(CodeFile).where(CodeFile.repo_id == repo_id)
    res = await db.execute(stmt)
    files = res.scalars().all()
    return [
        {
            "id": f.id,
            "file_path": f.file_path,
            "language": f.language,
            "total_lines": f.total_lines,
            "size_bytes": f.size_bytes
        }
        for f in files
    ]
