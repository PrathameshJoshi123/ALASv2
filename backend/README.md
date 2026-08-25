# Backend Server

A FastAPI + Celery backend skeleton with database support.

## Structure

```
backend/
├── __init__.py           # Package initialization
├── main.py               # FastAPI application entry point
├── config.py             # Configuration management (Pydantic Settings)
├── database.py           # Database setup (SQLAlchemy async)
├── worker.py             # Celery worker entry point
├── beat.py               # Celery beat scheduler entry point
├── .env                  # Environment variables
├── .env.example          # Example environment variables
├── requirements.txt      # Python dependencies
├── models/               # SQLAlchemy models
│   ├── __init__.py
│   └── base.py           # Base model classes
├── schemas/              # Pydantic schemas
│   ├── __init__.py
│   ├── response_schemas.py
│   └── task_schemas.py
├── routes/               # FastAPI route handlers
│   ├── __init__.py
│   ├── api.py            # Main API routes
│   └── tasks.py          # Celery task routes
├── tasks/                # Celery tasks
│   ├── __init__.py
│   └── example_tasks.py  # Example background tasks
├── services/             # Business logic layer
│   └── __init__.py
└── storage/              # File storage
    ├── uploads/          # Uploaded files
    ├── outputs/          # Processed outputs
    └── chroma/           # ChromaDB storage
```

## Quick Start

### Prerequisites

- Python 3.10+
- Redis server running
- PostgreSQL (optional, falls back to SQLite)

### Installation

1. Create virtual environment (if not exists):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Copy environment file:
   ```bash
   cp backend/.env.example backend/.env
   ```

4. Edit `backend/.env` with your settings.

### Running the Application

#### Development Server

```bash
# Start FastAPI server
cd backend
python -m uvicorn main:app --reload --port 8000

# Or from project root
python -m uvicorn backend.main:app --reload --port 8000
```

Access at: http://localhost:8000

#### Celery Worker

In a new terminal:

```bash
# Start Celery worker
celery -A backend.worker.celery_app worker --loglevel=info

# Or with specific queue
celery -A backend.worker.celery_app worker --loglevel=info --queues=high_priority
```

#### Celery Beat (Scheduler)

For periodic tasks:

```bash
celery -A backend.beat.celery_app beat --loglevel=info
```

## Configuration

Environment variables (see `.env.example`):

- `REDIS_URL` - Redis connection URL for caching
- `CELERY_BROKER_URL` - Celery broker URL (Redis)
- `CELERY_RESULT_BACKEND` - Celery result backend URL
- `POSTGRES_URL` - PostgreSQL connection URL
- `DATABASE_URL` - Alternative database URL
- `UPLOAD_DIR` - File upload directory
- `OUTPUT_DIR` - Processed file output directory
- `CHROMA_DIR` - ChromaDB storage directory
- `MISTRALAI_API_KEY` - Mistral AI API key
- `MISTRAL_MODEL` - Default Mistral model
- `MISTRAL_EMBEDDING_MODEL` - Mistral embedding model

## API Endpoints

### Health & Info

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /celery/health` - Celery health check
- `GET /db/health` - Database health check
- `GET /info` - API information

### API v1

- `GET /api/v1/` - API root
- `POST /api/v1/upload` - Upload file
- `GET /api/v1/files` - List uploaded files
- `GET /api/v1/config` - Get configuration

### Tasks

- `POST /tasks/submit/add` - Submit addition task
- `POST /tasks/submit/process-file` - Submit file processing task
- `POST /tasks/submit/long-running` - Submit long-running task
- `GET /tasks/{task_id}/status` - Check task status
- `GET /tasks/{task_id}/result` - Get task result
- `POST /tasks/{task_id}/revoke` - Revoke task
- `GET /tasks/queue` - Get queue status

### Documentation

- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc
- `GET /openapi.json` - OpenAPI schema

## Database

### SQLite (Default)

No configuration needed. Creates `test.db` in the backend directory.

### PostgreSQL

Set `POSTGRES_URL` or `DATABASE_URL` in `.env`:

```
POSTGRES_URL=postgresql://user:password@localhost:5432/database
```

### Creating Models

Add model files to `backend/models/`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import BaseModel, UUIDBaseModel

class User(BaseModel):
    __tablename__ = "users"
    
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
```

### Migrations

For production, use Alembic for migrations:

```bash
pip install alembic
alembic init migrations
# Edit alembic.ini and migrations/env.py
alembic revision --autogenerate -m "Initial models"
alembic upgrade head
```

## Adding New Features

### New API Route

1. Create a new file in `backend/routes/` (e.g., `users.py`)
2. Add router and endpoints
3. Import and include in `backend/main.py`

### New Celery Task

1. Create a new file in `backend/tasks/` (e.g., `user_tasks.py`)
2. Define tasks with `@shared_task` decorator
3. Tasks are auto-discovered in development
4. For production, add to `celery_app.conf.imports`

### New Schema

1. Create or update files in `backend/schemas/`
2. Use Pydantic BaseModel for validation
3. Import and use in routes

## Production Deployment

### Docker (Recommended)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend /app/backend
COPY .env /app/backend/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  worker:
    build: .
    command: celery -A backend.worker.celery_app worker --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis
      - web

  beat:
    build: .
    command: celery -A backend.beat.celery_app beat --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis
      - web

volumes:
  redis_data:
```

### Using Systemd

Create `/etc/systemd/system/backend-web.service`:

```ini
[Unit]
Description=Backend Web Server
After=network.target

[Service]
User=youruser
WorkingDirectory=/path/to/MajorProject
EnvironmentFile=/path/to/MajorProject/backend/.env
ExecStart=/path/to/MajorProject/venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/backend-worker.service`:

```ini
[Unit]
Description=Backend Celery Worker
After=network.target redis.target

[Service]
User=youruser
WorkingDirectory=/path/to/MajorProject
EnvironmentFile=/path/to/MajorProject/backend/.env
ExecStart=/path/to/MajorProject/venv/bin/celery -A backend.worker.celery_app worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping
# Should return: PONG
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -h localhost -U username -d database

# Test SQLite
sqlite3 backend/test.db "SELECT 1;"
```

### Celery Worker Not Starting

```bash
# Check if Redis is running
redis-cli info

# Check Celery logs
celery -A backend.worker.celery_app worker --loglevel=debug
```

## License

MIT
