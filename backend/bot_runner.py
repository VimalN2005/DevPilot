"""
DevPilot Standalone Bot Runner for GitHub Actions CI/CD.
Reads $GITHUB_EVENT_PATH and executes autonomous PR reviews or Issue triage directly inside GitHub Actions.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
from app.services.github_bot import github_bot


async def main():
    event_path = os.getenv("GITHUB_EVENT_PATH")
    event_name = os.getenv("GITHUB_EVENT_NAME", "pull_request")
    github_token = os.getenv("GITHUB_TOKEN")

    if github_token:
        settings.GITHUB_TOKEN = github_token

    print(f"[*] DevPilot Bot Runner Active")
    print(f"[*] Event: {event_name}")
    print(f"[*] Maintainer: @{settings.GITHUB_ADMIN_USER}")

    if not event_path or not Path(event_path).exists():
        print("[!] No GITHUB_EVENT_PATH detected. Simulating local test PR review...")
        sample_payload = {
            "action": "opened",
            "pull_request": {
                "number": 1,
                "title": "feat: community contribution",
                "user": {"login": "contributor"}
            },
            "repository": {
                "name": "DevPilot",
                "owner": {"login": settings.GITHUB_ADMIN_USER}
            },
            "diff_text": "diff --git a/auth.py b/auth.py\n+def logout(): session.clear()"
        }
        res = await github_bot.handle_pull_request_event(sample_payload)
        print("\n=== GENERATED BOT REVIEW ===")
        print(res["comment"])
        return

    payload = json.loads(Path(event_path).read_text(encoding="utf-8"))

    if event_name in ["pull_request", "pull_request_target"]:
        action = payload.get("action", "")
        if action in ["opened", "synchronize", "reopened"]:
            print(f"[*] Reviewing Pull Request #{payload.get('pull_request', {}).get('number')}...")
            res = await github_bot.handle_pull_request_event(payload)
            print(f"[+] Review Verdict: {res['verdict']} (Score: {res['score']}/100)")
            print(f"[+] Comment status: {res.get('post_result', {}).get('status')}")
        else:
            print(f"[-] Pull request action '{action}' skipped.")

    elif event_name == "issues":
        action = payload.get("action", "")
        if action == "opened":
            print(f"[*] Triaging Issue #{payload.get('issue', {}).get('number')}...")
            res = await github_bot.handle_issues_event(payload)
            print(f"[+] Triage Severity: {res['severity']}")
            print(f"[+] Comment status: {res.get('post_result', {}).get('status')}")
        else:
            print(f"[-] Issue action '{action}' skipped.")

    elif event_name == "issue_comment":
        action = payload.get("action", "")
        body = payload.get("comment", {}).get("body", "")
        if action == "created" and body.startswith("/devpilot"):
            print(f"[*] Executing slash command: '{body}'...")
            res = await github_bot.handle_comment_command(payload)
            print(f"[+] Command output: {res.get('post_result', {}).get('status')}")
        else:
            print("[-] Comment did not contain a /devpilot command.")


if __name__ == "__main__":
    asyncio.run(main())
