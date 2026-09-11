import pytest
from app.services.pr_reviewer import pr_reviewer


@pytest.mark.asyncio
async def test_pr_security_warning_flag():
    diff_with_jwt_leak = """
diff --git a/backend/app/api/v1/auth.py b/backend/app/api/v1/auth.py
index 12345..67890 100644
--- a/backend/app/api/v1/auth.py
+++ b/backend/app/api/v1/auth.py
@@ -80,4 +80,6 @@ def logout():
+    # Clear cookies on client side
+    session.clear()
+    return {"message": "Logged out"}
"""
    result = await pr_reviewer.review_pr("Add logout endpoint", diff_with_jwt_leak, pr_number=142)
    assert result["verdict"] == "CHANGES_REQUESTED"
    assert result["warning_count"] >= 1
    security_findings = [f for f in result["findings"] if f["category"] == "Security"]
    assert len(security_findings) >= 1
    assert "revoked" in security_findings[0]["issue"].lower()


@pytest.mark.asyncio
async def test_clean_pr():
    clean_diff = """
diff --git a/backend/app/utils.py b/backend/app/utils.py
--- a/backend/app/utils.py
+++ b/backend/app/utils.py
@@ -10,3 +10,5 @@
+def test_helper() -> str:
+    return "clean code with tests"
"""
    result = await pr_reviewer.review_pr("Add helper", clean_diff, pr_number=143)
    assert result["overall_score"] >= 80
