"""
Database configuration and session management using SQLAlchemy.
Supports PostgreSQL, SQLite, and other databases via connection string.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_database_url() -> str:
    """Get the database URL from settings."""
    return settings.database_url


# Create async engine
# For SQLite, we need to handle some specific settings
database_url = get_database_url()
if database_url.startswith("sqlite"):
    # SQLite doesn't support async well in some cases, but we'll try
    engine = create_async_engine(
        database_url.replace("sqlite:///", "sqlite+aiosqlite:///"),
        echo=settings.DEBUG,
        future=True,
    )
else:
    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

# Enable foreign keys for SQLite
if database_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
)

# Sync session factory (for migrations)
SyncEngine = create_async_engine(database_url).sync_engine
SyncSessionLocal = sessionmaker(bind=SyncEngine, autocommit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    Use with FastAPI's Depends().
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.
    Usage:
        async with get_db_context() as db:
            # use db
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables.
    Create all tables defined in models.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully.")


async def drop_db() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("Database tables dropped successfully.")


async def close_db() -> None:
    """Close all database connections."""
    await engine.dispose()
    print("Database connections closed.")
