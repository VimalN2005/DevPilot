from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings
from app.core.security import hash_password
from app.db.models import Base, User

from sqlalchemy import event
from sqlalchemy.engine import Engine

def _get_effective_db_url() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite+aiosqlite:///./"):
        rel_name = url.replace("sqlite+aiosqlite:///./", "")
        db_path = settings.BASE_DIR / rel_name
        return f"sqlite+aiosqlite:///{db_path.as_posix()}"
    return url

effective_db_url = _get_effective_db_url()

# Ensure database directory exists
if effective_db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False, "timeout": 30.0}
else:
    connect_args = {}

engine = create_async_engine(
    effective_db_url,
    echo=False,
    connect_args=connect_args,
    future=True
)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create tables and seed initial users."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default users if they do not exist
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == "admin@devpilot.ai"))
        admin = result.scalar_one_or_none()

        if not admin:
            users_to_seed = [
                User(
                    email="admin@devpilot.ai",
                    hashed_password=hash_password("DevPilot123!"),
                    full_name="Lead Architect (Admin)",
                    role="ADMIN"
                ),
                User(
                    email="developer@devpilot.ai",
                    hashed_password=hash_password("DevPilot123!"),
                    full_name="Staff Engineer (Developer)",
                    role="DEVELOPER"
                ),
                User(
                    email="viewer@devpilot.ai",
                    hashed_password=hash_password("DevPilot123!"),
                    full_name="Product Auditor (Viewer)",
                    role="VIEWER"
                )
            ]
            session.add_all(users_to_seed)
            await session.commit()
