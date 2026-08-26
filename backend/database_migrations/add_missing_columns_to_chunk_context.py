"""
Migration script to add missing columns to chunk_context table.

This migration adds the is_merged and merged_chunk_ids columns that were added
to the ChunkContext model but were missing from the database table.

Run this script once to update your database schema.
"""

import logging
from typing import Optional

from sqlalchemy import Boolean, JSON, text
from sqlalchemy.orm import Session

from backend.database import engine, SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def column_exists(session: Session, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = session.execute(
        text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name 
            AND column_name = :column_name
        """),
        {"table_name": table_name, "column_name": column_name}
    )
    return result.fetchone() is not None


def add_missing_columns_to_chunk_context() -> bool:
    """
    Add missing columns (is_merged, merged_chunk_ids) to the chunk_context table.
    
    Returns:
        True if any migration was applied, False if all columns already existed
    """
    logger.info("Starting migration: add missing columns to chunk_context table")
    
    applied_any = False
    
    with SessionLocal() as session:
        # Check and add is_merged column
        if not column_exists(session, "chunk_context", "is_merged"):
            logger.info("Adding is_merged column to chunk_context table...")
            session.execute(
                text("""
                    ALTER TABLE chunk_context 
                    ADD COLUMN is_merged BOOLEAN NOT NULL DEFAULT false
                """)
            )
            applied_any = True
        else:
            logger.info("Column 'is_merged' already exists in chunk_context table.")
        
        # Check and add merged_chunk_ids column
        if not column_exists(session, "chunk_context", "merged_chunk_ids"):
            logger.info("Adding merged_chunk_ids column to chunk_context table...")
            session.execute(
                text("""
                    ALTER TABLE chunk_context 
                    ADD COLUMN merged_chunk_ids JSON NOT NULL DEFAULT '[]'
                """)
            )
            applied_any = True
        else:
            logger.info("Column 'merged_chunk_ids' already exists in chunk_context table.")
        
        if applied_any:
            session.commit()
            logger.info("Migration completed. Missing columns added.")
        else:
            logger.info("Migration not needed - all columns already exist.")
        
        return applied_any


def verify_migration() -> None:
    """Verify that the migration was applied correctly."""
    logger.info("Verifying migration...")
    
    with SessionLocal() as session:
        # Check both columns exist
        required_columns = ["is_merged", "merged_chunk_ids"]
        for col in required_columns:
            if not column_exists(session, "chunk_context", col):
                raise RuntimeError(f"Column '{col}' does not exist in chunk_context table after migration!")
        
        logger.info("Verification passed. All required columns exist in chunk_context table.")


if __name__ == "__main__":
    try:
        applied = add_missing_columns_to_chunk_context()
        if applied:
            verify_migration()
            logger.info("Migration completed successfully!")
        else:
            logger.info("Migration not needed - all columns already exist.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
