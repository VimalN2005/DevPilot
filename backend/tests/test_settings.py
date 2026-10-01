import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_settings_get_and_update():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get settings
        res = await client.get("/api/v1/settings")
        assert res.status_code == 200
        data = res.json()
        assert "provider" in data
        assert "database_type" in data
        assert "rate_limit_per_min" in data

        # 2. Update settings
        res_post = await client.post("/api/v1/settings", json={
            "provider": "gemini",
            "model": "gemini-2.5-flash"
        })
        assert res_post.status_code == 200
        post_data = res_post.json()
        assert post_data["status"] == "success"
        assert post_data["model"] == "gemini-2.5-flash"

        # 3. Test connection simulation
        res_test = await client.post("/api/v1/settings/test-connection", json={
            "provider": "offline",
            "model": "gemini-2.5-flash"
        })
        assert res_test.status_code == 200
        test_data = res_test.json()
        assert test_data["status"] == "info"
