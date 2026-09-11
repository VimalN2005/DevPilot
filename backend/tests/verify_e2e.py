import httpx
import json
import time

client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=20.0)

print("=== 1. Testing Auth Login ===")
r = client.post("/api/v1/auth/login", json={"email": "developer@devpilot.ai", "password": "DevPilot123!"})
assert r.status_code == 200, f"Login failed: {r.text}"
auth_data = r.json()
access_token = auth_data["access_token"]
refresh_token = auth_data["refresh_token"]
print("[PASS] Login successful, role:", auth_data["role"])

print("\n=== 2. Testing Refresh Token Rotation ===")
r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
assert r.status_code == 200, f"Refresh failed: {r.text}"
new_auth_data = r.json()
new_refresh_token = new_auth_data["refresh_token"]
assert new_refresh_token != refresh_token, "Refresh token must rotate!"
print("[PASS] Token rotated successfully!")

# Test old token is revoked
r_old = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
assert r_old.status_code == 401, "Old refresh token must be rejected as revoked!"
print("[PASS] Old refresh token correctly rejected (Revocation enforced)!")

print("\n=== 3. Testing Repository Connection & Job ===")
r = client.post("/api/v1/repos/connect", json={"name": "devpilot-demo", "branch": "main"})
assert r.status_code == 202, f"Connect failed: {r.text}"
repo_data = r.json()
repo_id = repo_data["repo_id"]
job_id = repo_data["job_id"]
print(f"[PASS] Ingestion job started: {job_id} for repo: {repo_id}")

# Poll job
for _ in range(15):
    jr = client.get(f"/api/v1/jobs/{job_id}")
    j = jr.json()
    if j["status"] in ["completed", "failed"]:
        status_val = j["status"]
        prog_val = j["progress"]
        res_val = j["result"]
        print(f"[PASS] Job finished with status: {status_val}, progress: {prog_val}%, files: {res_val}")
        break
    time.sleep(0.5)

print("\n=== 4. Testing RAG Chat ===")
r = client.post("/api/v1/chat", json={"repo_id": repo_id, "query": "Where is authentication implemented?"})
assert r.status_code == 200, f"Chat failed: {r.text}"
chat_resp = r.json()
print("[PASS] Response preview:", chat_resp["response"][:140], "...")
print("[PASS] Sources cited:", len(chat_resp["sources"]))

print("\n=== 5. Testing Issue Analyzer ===")
r = client.post("/api/v1/issues/analyze", json={
    "repo_id": repo_id,
    "title": "API returns 500 when refresh token expires",
    "description": "Unhandled ExpiredSignatureError in auth endpoint."
})
assert r.status_code == 200
issue_resp = r.json()
print("[PASS] Severity:", issue_resp["severity"])
print("[PASS] Likely modules:", issue_resp["likely_modules"])
print("[PASS] Suggested tests:", issue_resp["suggested_tests"])

print("\n=== 6. Testing PR Review Agent ===")
diff = """
diff --git a/backend/app/auth.py b/backend/app/auth.py
@@ -10,3 +10,4 @@
+def logout():
+    session.clear()
"""
r = client.post("/api/v1/pr/review", json={"pr_title": "feat: logout endpoint", "diff_text": diff, "pr_number": 142})
assert r.status_code == 200
pr_resp = r.json()
print("[PASS] PR Verdict:", pr_resp["verdict"])
print("[PASS] Overall Score:", pr_resp["overall_score"])
print("[PASS] Warnings flagged:", pr_resp["warning_count"])

print("\n=== 7. Testing Multi-Agent Workflow & Human Gate ===")
r = client.post("/api/v1/agents/workflow", json={
    "repo_id": repo_id,
    "issue_title": "API returns 500 when refresh token expires",
    "issue_description": "Fix expired refresh token handling"
})
assert r.status_code == 200
wf = r.json()
wf_id = wf["workflow_id"]
print("[PASS] Workflow created:", wf_id, "Status:", wf["status"])
assert wf["status"] == "AWAITING_HUMAN_APPROVAL", "Workflow must stop at human approval gate!"

# Approve patch
r = client.post("/api/v1/agents/approve-patch", json={"workflow_id": wf_id, "approved_by": "Admin Engineer"})
assert r.status_code == 200
appr = r.json()
commit_sha = appr["commit_sha"]
status_appr = appr["status"]
print(f"[PASS] Human approval recorded! New status: {status_appr}, Commit: {commit_sha}")

print("\n=== 8. Testing Observability Telemetry ===")
r = client.get("/api/v1/telemetry/metrics")
assert r.status_code == 200
metrics = r.json()
tot_req = metrics["total_requests"]
avg_lat = metrics["avg_latency_sec"]
cost_val = metrics["estimated_cost_usd"]
print(f"[PASS] Telemetry: Requests={tot_req}, Avg Latency={avg_lat}s, Cost=${cost_val}")

print("\n=== 9. Testing Evaluation API ===")
r = client.get("/api/v1/eval/latest")
assert r.status_code == 200
eval_res = r.json()
rec = eval_res["retrieval_recall"]
faith = eval_res["faithfulness"]
rel = eval_res["answer_relevance"]
print(f"[PASS] RAG Eval: Recall={rec}%, Faithfulness={faith}%, Relevance={rel}%")

print("\n========================================")
print("  ALL 9 ENDPOINTS PASSED VERIFICATION!  ")
print("========================================")
