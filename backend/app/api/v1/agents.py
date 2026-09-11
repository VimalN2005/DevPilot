from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.agent_workflow import agent_workflow

router = APIRouter(prefix="/agents", tags=["Multi-Agent Workflow"])


class WorkflowRunRequest(BaseModel):
    repo_id: str
    issue_title: str
    issue_description: str


class ApprovePatchRequest(BaseModel):
    workflow_id: str
    approved_by: Optional[str] = "admin@devpilot.ai"


@router.post("/workflow")
async def run_agent_workflow(
    req: WorkflowRunRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute 5-stage agentic workflow:
    Planner -> Search -> Code Analysis -> Test -> Reviewer
    Stops before modifying code, outputting a proposed patch awaiting human approval.
    """
    result = await agent_workflow.execute_workflow(
        db=db,
        repo_id=req.repo_id,
        issue_title=req.issue_title,
        issue_description=req.issue_description
    )
    return result


@router.post("/approve-patch")
async def approve_patch(req: ApprovePatchRequest):
    """
    Human Approval Gate:
    Approve proposed patch and advance workflow to APPROVED_AND_COMMITTED status.
    """
    try:
        return agent_workflow.approve_patch(req.workflow_id, req.approved_by)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
