import pytest
from app.services.issue_analyzer import issue_analyzer
from app.db.session import AsyncSessionLocal, init_db
from app.db.models import Repository


@pytest.mark.asyncio
async def test_issue_severity_and_fix_generation():
    await init_db()
    async with AsyncSessionLocal() as session:
        result = await issue_analyzer.analyze_issue(
            db=session,
            repo_id="dummy_repo",
            title="API returns 500 when refresh token expires",
            description="Users get a 500 internal server error whenever their JWT refresh token is expired."
        )
        assert result["severity"] == "High"
        assert len(result["likely_modules"]) > 0
        assert "suggested_fix" in result
        assert len(result["suggested_tests"]) >= 2
        assert any("test_expired_refresh_token" in t for t in result["suggested_tests"])
