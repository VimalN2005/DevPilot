from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.pr_reviewer import pr_reviewer

router = APIRouter(prefix="/pr", tags=["PR Review Agent"])


class PRReviewRequest(BaseModel):
    pr_title: str
    diff_text: str
    pr_number: Optional[int] = 142


@router.post("/review")
async def review_pull_request(req: PRReviewRequest):
    """
    Multi-Dimensional PR Review Agent.
    Audits 8 categories: Code Quality, Security, SQL, API Design, Error Handling, Tests, Perf, Type Safety.
    """
    result = await pr_reviewer.review_pr(
        pr_title=req.pr_title,
        diff_text=req.diff_text,
        pr_number=req.pr_number
    )
    return result
