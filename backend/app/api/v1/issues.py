from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.issue_analyzer import issue_analyzer

router = APIRouter(prefix="/issues", tags=["AI Issue Analyzer"])


class IssueAnalyzeRequest(BaseModel):
    repo_id: str
    title: str
    description: str


@router.post("/analyze")
async def analyze_issue(
    req: IssueAnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    AI Issue Analyzer:
    Triage issue, determine severity, locate implicated modules, diagnose root cause,
    suggest surgical fix, generate regression tests, and prepare implementation plan.
    """
    result = await issue_analyzer.analyze_issue(
        db=db,
        repo_id=req.repo_id,
        title=req.title,
        description=req.description
    )
    return result
