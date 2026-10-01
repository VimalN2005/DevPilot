import hashlib
import hmac
import json
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.main import app
from app.services.github_bot import github_bot


@pytest.mark.asyncio
async def test_webhook_hmac_signature_verification():
    secret = "test_webhook_secret_key"
    payload_bytes = b'{"action": "ping"}'
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    invalid_sig = "sha256=wronghash1234567890abcdef"

    assert github_bot.verify_webhook_signature(payload_bytes, valid_sig, secret=secret) is True
    assert github_bot.verify_webhook_signature(payload_bytes, invalid_sig, secret=secret) is False
    assert github_bot.verify_webhook_signature(payload_bytes, None, secret=secret) is False


@pytest.mark.asyncio
async def test_webhook_pull_request_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pr_payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "title": "feat: add user authentication",
                "user": {"login": "contributor_friend"},
                "diff_url": None
            },
            "repository": {
                "name": "DevPilot",
                "owner": {"login": "VimalN2005"}
            },
            "diff_text": "diff --git a/auth.py b/auth.py\n+def logout(): session.clear()"
        }

        res = await client.post(
            "/api/v1/github/webhook",
            headers={"X-GitHub-Event": "pull_request"},
            json=pr_payload
        )
        assert res.status_code == 200
        data = res.json()
        assert data["event"] == "pull_request"
        assert data["pr_number"] == 42
        assert "verdict" in data
        assert "comment" in data
        assert "@VimalN2005" in data["comment"]
        assert "DevPilot Autonomous PR Review" in data["comment"]
        assert "8-Dimension Audit Scorecard" in data["comment"]


@pytest.mark.asyncio
async def test_webhook_issues_handling():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        issue_payload = {
            "action": "opened",
            "issue": {
                "number": 99,
                "title": "API returns 500 when refresh token expires",
                "body": "Unhandled ExpiredSignatureError in /api/v1/auth/refresh endpoint.",
                "user": {"login": "tester_friend"}
            },
            "repository": {
                "name": "DevPilot",
                "owner": {"login": "VimalN2005"}
            }
        }

        res = await client.post(
            "/api/v1/github/webhook",
            headers={"X-GitHub-Event": "issues"},
            json=issue_payload
        )
        assert res.status_code == 200
        data = res.json()
        assert data["event"] == "issues"
        assert data["issue_number"] == 99
        assert "severity" in data
        assert "comment" in data
        assert "@VimalN2005" in data["comment"]
        assert "DevPilot Automated Issue Triage" in data["comment"]


@pytest.mark.asyncio
async def test_maintainer_lock_on_merge_command():
    # 1. Non-admin friend tries to merge PR
    unauthorized_payload = {
        "action": "created",
        "issue": {"number": 101, "pull_request": {}},
        "comment": {"body": "/devpilot merge", "user": {"login": "friend_user"}},
        "repository": {"name": "DevPilot", "owner": {"login": "VimalN2005"}}
    }
    unauth_res = await github_bot.handle_comment_command(unauthorized_payload)
    assert "Permission Denied" in unauth_res["response"]
    assert "@VimalN2005" in unauth_res["response"]
    assert unauth_res["is_admin"] is False

    # 2. Maintainer @VimalN2005 merges PR
    authorized_payload = {
        "action": "created",
        "issue": {"number": 101, "pull_request": {}},
        "comment": {"body": "/devpilot merge", "user": {"login": "VimalN2005"}},
        "repository": {"name": "DevPilot", "owner": {"login": "VimalN2005"}}
    }
    auth_res = await github_bot.handle_comment_command(authorized_payload)
    assert "Successfully Merged by Maintainer @VimalN2005" in auth_res["response"]
    assert auth_res["is_admin"] is True


@pytest.mark.asyncio
async def test_webhook_slash_command_and_simulation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test simulation endpoint
        sim_res = await client.post(
            "/api/v1/github/simulate",
            json={
                "event_type": "issue_comment",
                "repo_name": "DevPilot",
                "owner": "VimalN2005",
                "number": 42,
                "command": "/devpilot review"
            }
        )
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["event"] == "issue_comment"
        assert "DevPilot Autonomous PR Review" in sim_data["response"]

        # 2. Test event history listing
        evt_res = await client.get("/api/v1/github/events")
        assert evt_res.status_code == 200
        evt_data = evt_res.json()
        assert evt_data["total_events"] >= 1
        assert "webhook_url" in evt_data
