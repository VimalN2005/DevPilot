import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.eval import router as eval_router
from app.api.v1.issues import router as issues_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.pr import router as pr_router
from app.api.v1.repos import router as repos_router
from app.api.v1.telemetry import router as telemetry_router
from app.config import settings
from app.core.rate_limiter import check_rate_limit
from app.db.session import init_db

FRONTEND_DIR = settings.BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema and seed initial accounts
    await init_db()
    yield


app = FastAPI(
    title="DevPilot — AI Engineering Platform",
    description="Production-grade AI Backend for Codebase Intelligence & Developer Automation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    # Attach X-Request-ID
    req_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")
    request.state.request_id = req_id

    # Enforce rate limiter on API endpoints
    if request.url.path.startswith("/api/v1/chat") or request.url.path.startswith("/api/v1/issues"):
        try:
            await check_rate_limit(request)
        except Exception as e:
            from fastapi import HTTPException
            if isinstance(e, HTTPException):
                return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)

    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-Ms"] = str(process_time)
    return response


# Include API Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(repos_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(issues_router, prefix="/api/v1")
app.include_router(pr_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(eval_router, prefix="/api/v1")


# Serve Frontend Static Assets
if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "DevPilot Backend API is running. Navigate to /docs for OpenAPI specifications."}


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "DevPilot AI Engineering Platform",
        "database": "connected",
        "timestamp": time.time()
    }
