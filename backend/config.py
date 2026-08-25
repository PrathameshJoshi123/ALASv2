"""
Configuration management using Pydantic Settings.
Loads from .env file and environment variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    APP_NAME: str = "MajorProject Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    
    # File Storage
    UPLOAD_DIR: Path = Path("backend/storage/uploads")
    OUTPUT_DIR: Path = Path("backend/storage/outputs")
    CHROMA_DIR: Path = Path("backend/storage/chroma")
    
    # Database
    POSTGRES_URL: Optional[str] = None
    DATABASE_URL: Optional[str] = None
    
    # API Keys
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-large-latest"
    MISTRAL_EMBEDDING_MODEL: str = "mistral-embed"
    
    # Feature Flags
    CONTRACT_ANALYSIS_ENABLED: bool = True
    WEB_RESEARCH_ENABLED: bool = True
    
    # Neo4j (optional)
    NEO4J_URI: Optional[str] = None
    NEO4J_USERNAME: Optional[str] = None
    NEO4J_PASSWORD: Optional[str] = None
    
    @field_validator("UPLOAD_DIR", "OUTPUT_DIR", "CHROMA_DIR")
    @classmethod
    def validate_paths(cls, v: Path) -> Path:
        """Ensure storage directories exist."""
        v = Path(v)
        v.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    @property
    def database_url(self) -> str:
        """Get the database URL, falling back to PostgreSQL."""
        return self.DATABASE_URL or self.POSTGRES_URL or "sqlite:///./test.db"
    
    def ensure_directories(self) -> None:
        """Create all required directories."""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.CHROMA_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
