"""
Migration script to create the contract_analysis, contract_obligations, and contract_risks tables.
"""

import logging
from sqlalchemy import inspect
from backend.database import engine
from backend.models.contract_analysis import ContractAnalysis, ContractObligation, ContractRisk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tables_if_not_exist() -> bool:
    """
    Create the contract analysis-related tables if they don't already exist.
    
    Returns:
        True if any tables were created, False if all already existed.
    """
    logger.info("Checking contract analysis tables...")
    inspector = inspect(engine)
    created_any = False
    
    # 1. contract_analysis
    if not inspector.has_table("contract_analysis"):
        logger.info("Table 'contract_analysis' does not exist. Creating table...")
        ContractAnalysis.__table__.create(bind=engine)
        logger.info("Table 'contract_analysis' created successfully.")
        created_any = True
    else:
        logger.info("Table 'contract_analysis' already exists.")
        
    # 2. contract_obligations
    if not inspector.has_table("contract_obligations"):
        logger.info("Table 'contract_obligations' does not exist. Creating table...")
        ContractObligation.__table__.create(bind=engine)
        logger.info("Table 'contract_obligations' created successfully.")
        created_any = True
    else:
        logger.info("Table 'contract_obligations' already exists.")
        
    # 3. contract_risks
    if not inspector.has_table("contract_risks"):
        logger.info("Table 'contract_risks' does not exist. Creating table...")
        ContractRisk.__table__.create(bind=engine)
        logger.info("Table 'contract_risks' created successfully.")
        created_any = True
    else:
        logger.info("Table 'contract_risks' already exists.")
        
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
