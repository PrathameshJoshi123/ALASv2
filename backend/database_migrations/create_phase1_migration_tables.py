"""
Migration script to create:
- document_extractions (replaces legacy disk JSON output files)
- contract_draft_versions (immutable snapshot audit history of drafts)
- contract_clauses (relational clause-level storage and redrafting tracking)
"""

import logging
from sqlalchemy import inspect
from backend.database import engine
from backend.models.document_extraction import DocumentExtraction
from backend.models.contract_draft import ContractDraftVersion
from backend.models.contract_analysis import ContractClause

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_phase1_tables_if_not_exist() -> bool:
    """
    Create phase 1 database tables and missing columns for fully database-backed
    contract drafting and analysis.
    Works for both PostgreSQL and SQLite.
    """
    logger.info("Checking Phase 1 tables (document_extractions, contract_draft_versions, contract_clauses)...")
    inspector = inspect(engine)
    created_any = False

    # 1. Ensure models tables are created if missing
    DocumentExtraction.__table__.create(bind=engine, checkfirst=True)
    ContractDraftVersion.__table__.create(bind=engine, checkfirst=True)
    ContractClause.__table__.create(bind=engine, checkfirst=True)

    is_postgres = engine.dialect.name == "postgresql"

    # 2. Check and add any missing columns in contract_clauses
    if inspector.has_table("contract_clauses"):
        existing_clause_cols = {col["name"] for col in inspector.get_columns("contract_clauses")}
        clause_cols = [
            ("original_raw_text", "TEXT"),
            ("is_revised", "BOOLEAN DEFAULT FALSE"),
            ("revision_rationale", "TEXT"),
            ("revised_at", "TIMESTAMP WITH TIME ZONE" if is_postgres else "DATETIME"),
            ("confidence_score", "FLOAT DEFAULT 0.85"),
        ]
        with engine.begin() as conn:
            for col_name, col_def in clause_cols:
                if col_name not in existing_clause_cols:
                    logger.info(f"Adding missing column '{col_name}' to 'contract_clauses' table...")
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE contract_clauses ADD COLUMN {col_name} {col_def}")
                        created_any = True
                    except Exception as e:
                        logger.warning(f"Could not add column '{col_name}' to contract_clauses: {e}")

    # 3. Check and add any missing columns in contract_draft_versions
    if inspector.has_table("contract_draft_versions"):
        existing_version_cols = {col["name"] for col in inspector.get_columns("contract_draft_versions")}
        version_cols = [
            ("change_summary", "TEXT"),
            ("created_by", "VARCHAR(50) DEFAULT 'ai_orchestrator'"),
        ]
        with engine.begin() as conn:
            for col_name, col_def in version_cols:
                if col_name not in existing_version_cols:
                    logger.info(f"Adding missing column '{col_name}' to 'contract_draft_versions' table...")
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE contract_draft_versions ADD COLUMN {col_name} {col_def}")
                        created_any = True
                    except Exception as e:
                        logger.warning(f"Could not add column '{col_name}' to contract_draft_versions: {e}")

    # 4. Check and add any missing columns in document_extractions
    if inspector.has_table("document_extractions"):
        existing_extraction_cols = {col["name"] for col in inspector.get_columns("document_extractions")}
        extraction_cols = [
            ("extracted_text", "TEXT"),
            ("status", "VARCHAR(50) DEFAULT 'COMPLETED'"),
        ]
        with engine.begin() as conn:
            for col_name, col_def in extraction_cols:
                if col_name not in existing_extraction_cols:
                    logger.info(f"Adding missing column '{col_name}' to 'document_extractions' table...")
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE document_extractions ADD COLUMN {col_name} {col_def}")
                        created_any = True
                    except Exception as e:
                        logger.warning(f"Could not add column '{col_name}' to document_extractions: {e}")

    return created_any


if __name__ == "__main__":
    try:
        created = create_phase1_tables_if_not_exist()
        if created:
            logger.info("Phase 1 database migration completed successfully!")
        else:
            logger.info("Phase 1 tables verified - already up to date.")
    except Exception as e:
        logger.error(f"Phase 1 migration failed: {e}")
        raise
