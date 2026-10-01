import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.services.github_bot import github_bot

router = APIRouter(prefix="/github", tags=["GitHub Bot & Webhooks"])


class SimulateWebhookRequest(BaseModel):
    event_type: str  # "pull_request", "issues", "issue_comment"
    repo_name: Optional[str] = "DevPilot"
    owner: Optional[str] = "VimalN2005"
    number: Optional[int] = 142
    title: Optional[str] = "feat: add user authentication and refresh token rotation"
    body: Optional[str] = "API returns 500 when refresh token expires. Please fix and add regression tests."
    diff_text: Optional[str] = None
    command: Optional[str] = "/devpilot review"


@router.post("/webhook")
async def receive_github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db)
):
    """
    Primary GitHub Webhook Ingestion Endpoint.
    Verifies HMAC SHA-256 signature and automatically triages issues or reviews pull requests.
    """
    body_bytes = await request.body()

    # 1. Verify HMAC-SHA256 signature if secret is configured
    if settings.GITHUB_WEBHOOK_SECRET and x_hub_signature_256:
        is_valid = github_bot.verify_webhook_signature(body_bytes, x_hub_signature_256)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub webhook HMAC-SHA256 signature."
            )

    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_type = x_github_event or payload.get("event_type", "ping")

    # Handle Ping event
    if event_type == "ping":
        return {
            "status": "pong",
            "zen": payload.get("zen", "Keep it logically awesome."),
            "bot": settings.GITHUB_BOT_NAME
        }

    # Handle Pull Request event
    if event_type == "pull_request":
        res = await github_bot.handle_pull_request_event(payload)
        return res

    # Handle Issue event
    if event_type == "issues":
        res = await github_bot.handle_issues_event(payload, db=db)
        return res

    # Handle Comment / Slash Command event
    if event_type == "issue_comment":
        res = await github_bot.handle_comment_command(payload, db=db)
        return res

    return {
        "status": "ignored",
        "event": event_type,
        "message": f"Event '{event_type}' received but not configured for automated bot action."
    }


@router.get("/events")
async def list_recent_events():
    """Retrieve history of recent GitHub webhook events and bot responses."""
    return {
        "bot_name": settings.GITHUB_BOT_NAME,
        "webhook_url": f"http://localhost:{settings.PORT}/api/v1/github/webhook",
        "has_webhook_secret": bool(settings.GITHUB_WEBHOOK_SECRET),
        "total_events": len(github_bot.recent_events),
        "events": github_bot.recent_events
    }


@router.post("/simulate")
async def simulate_webhook(req: SimulateWebhookRequest, db: AsyncSession = Depends(get_db)):
    """Simulate a GitHub webhook event locally for testing and live demonstrations."""
    if req.event_type == "pull_request":
        sample_diff = req.diff_text or (
            f"diff --git a/backend/app/auth.py b/backend/app/auth.py\n"
            "@@ -20,6 +20,12 @@\n"
            "+def logout():\n"
            "+    # Missing token revocation\n"
            "+    session.clear()\n"
            "+    return {'message': 'logged out'}\n"
        )
        payload = {
            "action": "opened",
            "pull_request": {
                "number": req.number,
                "title": req.title,
                "diff_url": None
            },
            "repository": {
                "name": req.repo_name,
                "owner": {"login": req.owner}
            },
            "diff_text": sample_diff
        }
        res = await github_bot.handle_pull_request_event(payload)
        return res

    elif req.event_type == "issues":
        payload = {
            "action": "opened",
            "issue": {
                "number": req.number,
                "title": req.title,
                "body": req.body
            },
            "repository": {
                "name": req.repo_name,
                "owner": {"login": req.owner}
            }
        }
        res = await github_bot.handle_issues_event(payload, db=db)
        return res

    elif req.event_type == "issue_comment":
        payload = {
            "action": "created",
            "issue": {
                "number": req.number,
                "pull_request": {}
            },
            "comment": {
                "body": req.command
            },
            "repository": {
                "name": req.repo_name,
                "owner": {"login": req.owner}
            }
        }
        res = await github_bot.handle_comment_command(payload, db=db)
        return res

    raise HTTPException(status_code=400, detail=f"Unknown event type: {req.event_type}")
