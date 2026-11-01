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

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Create sync engine
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}
if not database_url.startswith("sqlite"):
    engine_kwargs["pool_size"] = 15
    engine_kwargs["max_overflow"] = 15
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_timeout"] = 30
    engine_kwargs["connect_args"] = {
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }

engine = create_engine(database_url, **engine_kwargs)

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


def run_migrations_safely() -> None:
    """
    Run column migrations for missing fields. Can be executed asynchronously or on demand.
    """
    logger = logging.getLogger(__name__)
    try:
        from backend.database_migrations.create_contract_analysis_tables import create_tables_if_not_exist
        create_tables_if_not_exist()
    except Exception as e:
        logger.warning(f"Schema migration check failed: {e}")
    try:
        from backend.database_migrations.create_phase1_migration_tables import create_phase1_tables_if_not_exist
        create_phase1_tables_if_not_exist()
    except Exception as e:
        logger.warning(f"Phase 1 schema migration check failed: {e}")


def init_db(run_heavy_migrations: bool = False) -> None:
    """
    Initialize database tables quickly.
    Runs Base.metadata.create_all() which creates missing tables in ~0.1s.
    Heavy column introspection migrations can be run in the background or when explicitly enabled.
    """
    Base.metadata.create_all(bind=engine)
    if run_heavy_migrations or getattr(settings, "AUTO_RUN_MIGRATIONS", False):
        run_migrations_safely()
    logging.getLogger(__name__).info("Database tables initialized successfully.")


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
