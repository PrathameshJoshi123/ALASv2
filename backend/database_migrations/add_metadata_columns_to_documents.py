"""
Database migration: Add metadata columns to documents table.

Adds the following columns to the documents table:
- counterparty_name: String(255), nullable
- contract_type: String(100), nullable, default='Service Agreement'
- status: String(50), nullable, default='uploaded'

This migration ensures the documents table has all the fields needed by the
updated Document model and the frontend application.

Usage:
    python backend/database_migrations/add_metadata_columns_to_documents.py
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Temporarily override DEBUG to avoid config issues
os.environ['DEBUG'] = 'true'

from backend.database import engine
from sqlalchemy import text


def migrate() -> None:
    """Apply migration to add metadata columns to documents table."""
    print("Running migration: add_metadata_columns_to_documents")
    
    # Check if columns already exist
    with engine.connect() as conn:
        # Check for PostgreSQL
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'documents' 
            AND column_name IN ('counterparty_name', 'contract_type', 'status')
        """))
        existing_columns = [row[0] for row in result.fetchall()]
        
        missing_columns = []
        if 'counterparty_name' not in existing_columns:
            missing_columns.append('counterparty_name')
        if 'contract_type' not in existing_columns:
            missing_columns.append('contract_type')
        if 'status' not in existing_columns:
            missing_columns.append('status')
        
        if not missing_columns:
            print("All required columns already exist. Migration not needed.")
            return
        
        print(f"Adding missing columns: {missing_columns}")
        
        # Add columns with appropriate SQL for the database type
        database_url = str(engine.url)
        
        if database_url.startswith('postgresql'):
            # PostgreSQL
            for col in missing_columns:
                if col == 'counterparty_name':
                    conn.execute(text("ALTER TABLE documents ADD COLUMN counterparty_name VARCHAR(255)"))
                elif col == 'contract_type':
                    conn.execute(text("ALTER TABLE documents ADD COLUMN contract_type VARCHAR(100) DEFAULT 'Service Agreement'"))
                elif col == 'status':
                    conn.execute(text("ALTER TABLE documents ADD COLUMN status VARCHAR(50) DEFAULT 'uploaded'"))
                    # Update existing rows to have the default status
                    conn.execute(text("UPDATE documents SET status = 'uploaded' WHERE status IS NULL"))
                print(f"Added column: {col}")
            
            conn.commit()
            
        elif database_url.startswith('sqlite'):
            # SQLite - check columns differently
            result = conn.execute(text("PRAGMA table_info(documents)"))
            existing_cols = [row[1] for row in result.fetchall()]
            
            for col in missing_columns:
                if col not in existing_cols:
                    if col == 'counterparty_name':
                        conn.execute(text("ALTER TABLE documents ADD COLUMN counterparty_name TEXT"))
                    elif col == 'contract_type':
                        conn.execute(text("ALTER TABLE documents ADD COLUMN contract_type TEXT DEFAULT 'Service Agreement'"))
                    elif col == 'status':
                        conn.execute(text("ALTER TABLE documents ADD COLUMN status TEXT DEFAULT 'uploaded'"))
                    print(f"Added column: {col}")
            
            conn.commit()
        else:
            print(f"Unsupported database: {database_url}")
            return
    
    print("Migration completed successfully.")


if __name__ == "__main__":
    migrate()
