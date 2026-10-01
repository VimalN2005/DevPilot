import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import httpx
from app.config import settings

router = APIRouter(prefix="/settings", tags=["Platform Settings"])


class SettingsUpdateRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    github_token: Optional[str] = None
    ollama_base_url: Optional[str] = None


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model: Optional[str] = None


def mask_key(key: Optional[str]) -> str:
    if not key or len(key) < 8:
        return ""
    return f"{key[:4]}...{key[-4:]}"


@router.get("")
async def get_settings():
    """Retrieve current platform settings with masked credentials."""
    db_type = "PostgreSQL (pgvector)" if "postgres" in settings.DATABASE_URL else "SQLite (WAL)"
    return {
        "provider": settings.DEFAULT_LLM_PROVIDER,
        "model": settings.DEFAULT_MODEL,
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "gemini_key_masked": mask_key(settings.GEMINI_API_KEY),
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "openai_key_masked": mask_key(settings.OPENAI_API_KEY),
        "has_github_token": bool(settings.GITHUB_TOKEN),
        "github_token_masked": mask_key(settings.GITHUB_TOKEN),
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "rate_limit_per_min": settings.RATE_LIMIT_PER_MINUTE,
        "database_type": db_type,
        "environment": settings.ENVIRONMENT
    }


@router.post("")
async def update_settings(req: SettingsUpdateRequest):
    """Update runtime settings and persist to .env file."""
    env_path = settings.BASE_DIR / ".env"
    env_lines = []

    if env_path.exists():
        env_lines = env_path.read_text(encoding="utf-8").splitlines()

    env_dict = {}
    for line in env_lines:
        line_strip = line.strip()
        if line_strip and not line_strip.startswith("#") and "=" in line_strip:
            k, v = line_strip.split("=", 1)
            env_dict[k.strip()] = v.strip()

    # Update settings object & env_dict
    if req.provider is not None:
        settings.DEFAULT_LLM_PROVIDER = req.provider
        env_dict["DEFAULT_LLM_PROVIDER"] = req.provider

    if req.model is not None:
        settings.DEFAULT_MODEL = req.model
        env_dict["DEFAULT_MODEL"] = req.model

    if req.gemini_api_key is not None:
        settings.GEMINI_API_KEY = req.gemini_api_key.strip() or None
        env_dict["GEMINI_API_KEY"] = req.gemini_api_key.strip()

    if req.openai_api_key is not None:
        settings.OPENAI_API_KEY = req.openai_api_key.strip() or None
        env_dict["OPENAI_API_KEY"] = req.openai_api_key.strip()

    if req.github_token is not None:
        settings.GITHUB_TOKEN = req.github_token.strip() or None
        env_dict["GITHUB_TOKEN"] = req.github_token.strip()

    if req.ollama_base_url is not None:
        settings.OLLAMA_BASE_URL = req.ollama_base_url.strip()
        env_dict["OLLAMA_BASE_URL"] = req.ollama_base_url.strip()

    # Reconstruct .env preserving comments
    new_lines = []
    keys_written = set()

    for line in env_lines:
        line_strip = line.strip()
        if line_strip and not line_strip.startswith("#") and "=" in line_strip:
            k = line_strip.split("=", 1)[0].strip()
            if k in env_dict:
                new_lines.append(f"{k}={env_dict[k]}")
                keys_written.add(k)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for k, v in env_dict.items():
        if k not in keys_written:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return {
        "status": "success",
        "message": "Settings updated and saved successfully.",
        "provider": settings.DEFAULT_LLM_PROVIDER,
        "model": settings.DEFAULT_MODEL
    }


@router.post("/test-connection")
async def test_connection(req: TestConnectionRequest):
    """Test connectivity with LLM provider."""
    provider = req.provider.lower()
    api_key = req.api_key or (settings.GEMINI_API_KEY if provider == "gemini" else settings.OPENAI_API_KEY)
    model = req.model or settings.DEFAULT_MODEL

    if provider == "gemini":
        if not api_key:
            raise HTTPException(status_code=400, detail="Gemini API Key is required.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model if 'gemini' in model else 'gemini-2.5-flash'}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json={"contents": [{"parts": [{"text": "Hello, respond with 'OK'"}]}]})
                if res.status_code == 200:
                    return {"status": "success", "message": "Gemini connection verified successfully!"}
                else:
                    return {"status": "error", "message": f"Gemini error {res.status_code}: {res.text[:200]}"}
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

    elif provider == "openai":
        if not api_key:
            raise HTTPException(status_code=400, detail="OpenAI API Key is required.")
        url = "https://api.openai.com/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model if "gpt" in model else "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5}
                )
                if res.status_code == 200:
                    return {"status": "success", "message": "OpenAI connection verified successfully!"}
                else:
                    return {"status": "error", "message": f"OpenAI error {res.status_code}: {res.text[:200]}"}
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

    elif provider == "ollama":
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        url = f"{base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    return {"status": "success", "message": "Local Ollama server connected successfully!"}
                return {"status": "error", "message": f"Ollama response code {res.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Could not reach Ollama: {str(e)}"}

    return {"status": "info", "message": "Offline simulation mode active."}
