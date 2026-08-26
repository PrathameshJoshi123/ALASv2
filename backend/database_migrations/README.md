# Database Migrations

This directory contains migration scripts to update the database schema when model changes are made.

## Available Migrations

### 1. `add_sequence_number_to_chunks.py`

Adds the `sequence_number` column to the `chunks` table.

**Why needed**: The `sequence_number` column was added to the `Chunk` SQLAlchemy model but the database table was not updated.

**What it does**:
- Adds `sequence_number INTEGER NOT NULL DEFAULT 0` column
- Creates an index on `sequence_number` for better query performance
- Updates existing rows with sequential numbers based on `created_at` timestamp

**Run it**:
```bash
cd /d/My_Space/MajorProject
source venv/Scripts/activate
PYTHONPATH=. python backend/database_migrations/add_sequence_number_to_chunks.py
```

### 2. `add_missing_columns_to_chunk_context.py`

Adds missing columns to the `chunk_context` table.

**Why needed**: The `is_merged` and `merged_chunk_ids` columns were added to the `ChunkContext` SQLAlchemy model but the database table was not updated.

**What it does**:
- Adds `is_merged BOOLEAN NOT NULL DEFAULT false` column
- Adds `merged_chunk_ids JSON NOT NULL DEFAULT '[]'` column

**Run it**:
```bash
cd /d/My_Space/MajorProject
source venv/Scripts/activate
PYTHONPATH=. python backend/database_migrations/add_missing_columns_to_chunk_context.py
```

## Running All Migrations

To ensure your database is up to date, run all migration scripts:

```bash
cd /d/My_Space/MajorProject
source venv/Scripts/activate
PYTHONPATH=. python backend/database_migrations/add_sequence_number_to_chunks.py
PYTHONPATH=. python backend/database_migrations/add_missing_columns_to_chunk_context.py
```

## Notes

- Each migration script checks if the columns already exist before attempting to add them
- Migrations are idempotent - running them multiple times won't cause errors
- Always back up your database before running migrations
- These scripts use SQLAlchemy to connect to the database configured in your `.env` file

## Future Improvements

Consider implementing a proper migration system like:
- Alembic (for SQLAlchemy)
- Django Migrations
- Or a simple version tracking system in the database
