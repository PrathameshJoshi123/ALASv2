"""
Migration script to add sequence_number column to chunks table.

This migration adds the sequence_number column that was added to the Chunk model
but was missing from the database table.

Run this script once to update your database schema.
"""

import logging
from typing import Optional

from sqlalchemy import Integer, text
from sqlalchemy.orm import Session

from backend.database import engine, SessionLocal
from backend.services.chunking.database import Chunk

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


def add_sequence_number_column() -> bool:
    """
    Add the sequence_number column to the chunks table if it doesn't exist.
    
    Returns:
        True if migration was applied, False if already existed
    """
    logger.info("Starting migration: add sequence_number to chunks table")
    
    with SessionLocal() as session:
        # Check if column already exists
        if column_exists(session, "chunks", "sequence_number"):
            logger.info("Column 'sequence_number' already exists in chunks table. Migration not needed.")
            return False
        
        try:
            # Add the column with a default value
            logger.info("Adding sequence_number column to chunks table...")
            session.execute(
                text("""
                    ALTER TABLE chunks 
                    ADD COLUMN sequence_number INTEGER NOT NULL DEFAULT 0
                """)
            )
            
            # Create index on sequence_number for better query performance
            logger.info("Creating index on sequence_number column...")
            session.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_sequence_number 
                    ON chunks(sequence_number)
                """)
            )
            
            # Update existing rows to have proper sequence numbers
            logger.info("Updating existing chunks with sequence numbers...")
            # Get all chunks ordered by id (or created_at) to assign sequence numbers
            result = session.execute(
                text("""
                    SELECT id 
                    FROM chunks 
                    ORDER BY created_at ASC, id ASC
                """)
            )
            chunk_ids = [row[0] for row in result.fetchall()]
            
            for idx, chunk_id in enumerate(chunk_ids, start=1):
                session.execute(
                    text("""
                        UPDATE chunks 
                        SET sequence_number = :sequence_number 
                        WHERE id = :id
                    """),
                    {"sequence_number": idx, "id": chunk_id}
                )
            
            session.commit()
            logger.info(f"Migration completed. Updated {len(chunk_ids)} chunks with sequence numbers.")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Migration failed: {e}")
            raise


def verify_migration() -> None:
    """Verify that the migration was applied correctly."""
    logger.info("Verifying migration...")
    
    with SessionLocal() as session:
        # Check column exists
        if not column_exists(session, "chunks", "sequence_number"):
            raise RuntimeError("sequence_number column does not exist after migration!")
        
        # Check some data
        result = session.execute(text("SELECT COUNT(*) FROM chunks"))
        total_chunks = result.scalar()
        
        if total_chunks > 0:
            result = session.execute(
                text("SELECT MIN(sequence_number), MAX(sequence_number) FROM chunks")
            )
            min_seq, max_seq = result.fetchone()
            logger.info(f"Verification passed. Chunks have sequence numbers from {min_seq} to {max_seq}")
        else:
            logger.info("Verification passed. No chunks in database.")


if __name__ == "__main__":
    try:
        applied = add_sequence_number_column()
        if applied:
            verify_migration()
            logger.info("Migration completed successfully!")
        else:
            logger.info("Migration not needed - column already exists.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
