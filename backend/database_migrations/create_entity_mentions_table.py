"""
Migration script to create the entity_mentions table.
"""

import logging
from sqlalchemy import inspect
from backend.database import engine
from backend.models.entity_mention import EntityMention

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_table_if_not_exists() -> bool:
    """
    Create the entity_mentions table if it doesn't already exist in the database.
    
    Returns:
        True if the table was created, False if it already existed.
    """
    logger.info("Checking if entity_mentions table exists...")
    inspector = inspect(engine)
    
    if not inspector.has_table("entity_mentions"):
        logger.info("Table 'entity_mentions' does not exist. Creating table...")
        EntityMention.__table__.create(bind=engine)
        logger.info("Table 'entity_mentions' created successfully.")
        return True
    else:
        logger.info("Table 'entity_mentions' already exists. No action taken.")
        return False


if __name__ == "__main__":
    try:
        created = create_table_if_not_exists()
        if created:
            logger.info("Migration completed successfully!")
        else:
            logger.info("Migration checked - table already exists.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
