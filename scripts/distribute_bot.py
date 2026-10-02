"""
DevPilot Multi-Repository Bot Installer
Distributes .github/workflows/devpilot.yml to all non-fork repositories of @VimalN2005.

Supports:
1. Git CLI Mode (uses local Git Credential Manager)
2. GitHub REST API Mode (uses GITHUB_TOKEN or Personal Access Token)
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKFLOW_CONTENT = """name: DevPilot Autonomous Bot

on:
  pull_request_target:
    types: [opened, synchronize, reopened]
  issues:
    types: [opened]
  issue_comment:
    types: [created]

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  devpilot:
    runs-on: ubuntu-latest
    steps:
      - name: Run DevPilot AI Reviewer & Triage Bot
        uses: VimalN2005/DevPilot@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          admin-user: "VimalN2005"
"""

GITHUB_USER = "VimalN2005"


def get_all_non_fork_repos(token=None):
    """Fetch all repositories owned by user and exclude forked repos."""
    url = f"https://api.github.com/users/{GITHUB_USER}/repos?per_page=100"
    headers = {"User-Agent": "DevPilot-Distributor"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        repos = json.loads(resp.read().decode("utf-8"))

    # Exclude forks and exclude DevPilot itself
    non_forks = [
        r for r in repos
        if not r.get("fork") and r.get("name").lower() != "devpilot"
    ]
    return non_forks


def install_via_api(repo_name, default_branch, token, dry_run=False):
    """Install workflow file via GitHub REST API."""
    file_path = ".github/workflows/devpilot.yml"
    url = f"https://api.github.com/repos/{GITHUB_USER}/{repo_name}/contents/{file_path}"
    headers = {
        "User-Agent": "DevPilot-Distributor",
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    # Check if file exists
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha = data.get("sha")
            print(f"  [i] Existing workflow found in {repo_name} (sha: {sha[:7]})")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    if dry_run:
        action_verb = "Update" if sha else "Create"
        print(f"  [DRY-RUN] Would {action_verb} {file_path} in {repo_name} (branch: {default_branch})")
        return True

    payload = {
        "message": "ci(devpilot): install autonomous AI review & triage bot (@VimalN2005)",
        "content": base64.b64encode(WORKFLOW_CONTENT.encode("utf-8")).decode("utf-8"),
        "branch": default_branch
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status in [200, 201]:
                print(f"  [+] Successfully deployed workflow to {repo_name} via API!")
                return True
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print(f"  [-] API Error ({e.code}) on {repo_name}: {err_msg[:200]}")
        return False

    return False


def install_via_git(repo_name, clone_url, default_branch, dry_run=False):
    """Install workflow file via local git clone and push."""
    temp_dir = Path(tempfile.mkdtemp(prefix=f"devpilot_{repo_name}_"))
    try:
        if dry_run:
            print(f"  [DRY-RUN] Would clone {clone_url}, add .github/workflows/devpilot.yml, and push to {default_branch}")
            return True

        # 1. Shallow clone
        clone_cmd = ["git", "clone", "--depth", "1", "--branch", default_branch, clone_url, str(temp_dir)]
        res = subprocess.run(clone_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  [-] Failed to clone {repo_name}: {res.stderr[:200]}")
            return False

        # 2. Create workflow path
        wf_dir = temp_dir / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        wf_file = wf_dir / "devpilot.yml"

        if wf_file.exists() and wf_file.read_text(encoding="utf-8") == WORKFLOW_CONTENT:
            print(f"  [=] {repo_name} already has latest DevPilot workflow. Skipping.")
            return True

        wf_file.write_text(WORKFLOW_CONTENT, encoding="utf-8")

        # 3. Git commit & push
        subprocess.run(["git", "-C", str(temp_dir), "add", ".github/workflows/devpilot.yml"], check=True)
        status_res = subprocess.run(["git", "-C", str(temp_dir), "status", "--porcelain"], capture_output=True, text=True)
        if not status_res.stdout.strip():
            print(f"  [=] No changes in {repo_name}. Skipping.")
            return True

        commit_cmd = [
            "git", "-C", str(temp_dir),
            "commit", "-m", "ci(devpilot): install autonomous AI review & triage bot (@VimalN2005)"
        ]
        res = subprocess.run(commit_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  [-] Commit error on {repo_name}: {res.stderr[:200]}")
            return False

        push_cmd = ["git", "-C", str(temp_dir), "push", "origin", default_branch]
        res = subprocess.run(push_cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  [+] Successfully deployed workflow to {repo_name} via Git!")
            return True
        else:
            print(f"  [-] Push error on {repo_name}: {res.stderr[:200]}")
            return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Distribute DevPilot bot across all non-fork repos")
    parser.add_argument("--repo", help="Install to a single specific repository for testing", default=None)
    parser.add_argument("--mode", choices=["git", "api"], default="git", help="Installation mode (git or api)")
    parser.add_argument("--token", help="GitHub Personal Access Token (for API mode)", default=os.getenv("GITHUB_TOKEN"))
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without committing or pushing")
    args = parser.parse_args()

    print("=" * 60)
    print(f"🚀 DevPilot Bot Multi-Repo Installer")
    print(f"Maintainer: @{GITHUB_USER}")
    print(f"Mode: {args.mode.upper()}")
    print(f"Dry Run: {args.dry_run}")
    print("=" * 60)

    try:
        repos = get_all_non_fork_repos(token=args.token)
    except Exception as e:
        print(f"[-] Failed to fetch repository list: {e}")
        return

    if args.repo:
        repos = [r for r in repos if r["name"].lower() == args.repo.lower()]
        if not repos:
            print(f"[-] Repository '{args.repo}' not found among non-fork repositories.")
            return

    print(f"[*] Found {len(repos)} non-fork repositories to process.\n")

    successful = 0
    failed = 0

    for idx, r in enumerate(repos, 1):
        name = r["name"]
        branch = r.get("default_branch", "main")
        clone_url = r.get("clone_url")

        print(f"[{idx}/{len(repos)}] Processing: {name} (branch: {branch})")

        ok = False
        if args.mode == "api":
            if not args.token:
                print("[-] Error: --token or GITHUB_TOKEN required for API mode.")
                return
            ok = install_via_api(name, branch, args.token, dry_run=args.dry_run)
        else:
            ok = install_via_git(name, clone_url, branch, dry_run=args.dry_run)

        if ok:
            successful += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"🎉 Installation Run Finished!")
    print(f"Successful: {successful}/{len(repos)}")
    print(f"Failed/Skipped: {failed}/{len(repos)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
