"""
Migration script to create the contract_analysis, contract_obligations, and contract_risks tables.
"""

import logging
from sqlalchemy import inspect
from backend.database import engine
from backend.models.contract_analysis import ContractAnalysis, ContractObligation, ContractRisk, ContractChatMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tables_if_not_exist() -> bool:
    """
    Create contract analysis-related tables if missing and add missing columns.
    Works for both PostgreSQL and SQLite.
    
    Returns:
        True if any tables/columns were created, False otherwise.
    """
    logger.info("Checking contract analysis tables and columns...")
    inspector = inspect(engine)
    created_any = False
    
    # 1. Ensure models are created if tables don't exist
    ContractAnalysis.__table__.create(bind=engine, checkfirst=True)
    ContractObligation.__table__.create(bind=engine, checkfirst=True)
    ContractRisk.__table__.create(bind=engine, checkfirst=True)
    ContractChatMessage.__table__.create(bind=engine, checkfirst=True)

    is_postgres = engine.dialect.name == "postgresql"

    # 2. Migration for documents table missing columns
    if inspector.has_table("documents"):
        existing_doc_cols = {col["name"] for col in inspector.get_columns("documents")}
        doc_cols = [
            ("counterparty_name", "VARCHAR(255)"),
            ("company_name", "VARCHAR(255)"),
            ("contract_type", "VARCHAR(100)"),
            ("status", "VARCHAR(50) DEFAULT 'UPLOADED'"),
        ]
        with engine.begin() as conn:
            for col_name, col_def in doc_cols:
                if col_name not in existing_doc_cols:
                    logger.info(f"Adding missing column '{col_name}' to 'documents' table...")
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE documents ADD COLUMN {col_name} {col_def}")
                        created_any = True
                    except Exception as e:
                        logger.warning(f"Could not add column '{col_name}' to documents: {e}")

    # 3. Migration for contract_analysis table missing columns
    if inspector.has_table("contract_analysis"):
        existing_cols = {col["name"] for col in inspector.get_columns("contract_analysis")}
        
        json_type = "JSONB" if is_postgres else "JSON"
        json_default = "'[]'::jsonb" if is_postgres else "'[]'"
        
        new_cols = [
            ("overall_risk_score", "FLOAT DEFAULT 0.0"),
            ("critical_issues", "INTEGER DEFAULT 0"),
            ("high_issues", "INTEGER DEFAULT 0"),
            ("medium_issues", "INTEGER DEFAULT 0"),
            ("low_issues", "INTEGER DEFAULT 0"),
            ("recommended_actions", f"{json_type} DEFAULT {json_default}"),
            ("clauses", f"{json_type} DEFAULT {json_default}"),
            ("legal_sources", f"{json_type} DEFAULT {json_default}"),
        ]
        with engine.begin() as conn:
            for col_name, col_def in new_cols:
                if col_name not in existing_cols:
                    logger.info(f"Adding missing column '{col_name}' to 'contract_analysis' table...")
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE contract_analysis ADD COLUMN {col_name} {col_def}")
                        created_any = True
                    except Exception as e:
                        logger.warning(f"Could not add column '{col_name}' to contract_analysis: {e}")

    # 4. Migration for contract_obligations table missing columns
    if inspector.has_table("contract_obligations"):
        existing_ob_cols = {col["name"] for col in inspector.get_columns("contract_obligations")}
        if "category" not in existing_ob_cols:
            logger.info("Adding missing column 'category' to 'contract_obligations' table...")
            with engine.begin() as conn:
                try:
                    conn.exec_driver_sql("ALTER TABLE contract_obligations ADD COLUMN category VARCHAR(100) DEFAULT 'General'")
                    created_any = True
                except Exception as e:
                    logger.warning(f"Could not add column 'category' to contract_obligations: {e}")

    # 5. Migration for contract_risks table missing columns
    if inspector.has_table("contract_risks"):
        existing_risk_cols = {col["name"] for col in inspector.get_columns("contract_risks")}
        if "category" not in existing_risk_cols:
            logger.info("Adding missing column 'category' to 'contract_risks' table...")
            with engine.begin() as conn:
                try:
                    conn.exec_driver_sql("ALTER TABLE contract_risks ADD COLUMN category VARCHAR(100) DEFAULT 'General'")
                    created_any = True
                except Exception as e:
                    logger.warning(f"Could not add column 'category' to contract_risks: {e}")

    return created_any


if __name__ == "__main__":
    try:
        created = create_tables_if_not_exist()
        if created:
            logger.info("Migration completed successfully!")
        else:
            logger.info("Migration checked - tables already exist.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
