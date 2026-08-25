"""
Database configuration and session management using SQLAlchemy.
Synchronous version - no async support.
Supports PostgreSQL, SQLite, and other databases via connection string.
"""

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_database_url() -> str:
    """Get the database URL from settings."""
    return settings.database_url


# Get and normalize database URL
database_url = get_database_url()

# For PostgreSQL, ensure sync driver
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://")
elif database_url.startswith("sqlite"):
    # Keep SQLite as-is for sync
    pass

# Create sync engine
engine = create_engine(
    database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Enable foreign keys for SQLite
if database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Sync engine for migrations
SyncEngine = engine
SyncSessionLocal = sessionmaker(bind=SyncEngine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a synchronous database session.
    Use with FastAPI's Depends().
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()



def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for synchronous database sessions.
    Usage:
        with get_db_context() as db:
            # use db
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Initialize database tables.
    Create all tables defined in models.
    """
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")


def drop_db() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    """
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped successfully.")


def close_db() -> None:
    """Close all database connections."""
    engine.dispose()
    print("Database connections closed.")
