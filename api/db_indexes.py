"""
CouchDB index initialization for Moirai.

Run once on deployment or database setup to create performance indexes.
This script is idempotent - safe to run multiple times.

Usage:
    python -c "from api.db_indexes import initialize_all_indexes; initialize_all_indexes()"
    
Or directly:
    python api/db_indexes.py
"""
import logging
import requests
from typing import Dict, List
from api.db_config import get_couchdb_uri

logger = logging.getLogger(__name__)


def create_index(db_name: str, index_def: Dict) -> bool:
    """
    Create a single index in CouchDB.
    
    Args:
        db_name: Database name
        index_def: Index definition dict
        
    Returns:
        True if successful, False otherwise
    """
    db_url = get_couchdb_uri().rstrip('/')
    
    try:
        response = requests.post(
            f"{db_url}/{db_name}/_index",
            json=index_def,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Check if index was created or already existed
        if result.get("result") == "created":
            logger.info(f"✓ Created index: {index_def['name']} in {db_name}")
        elif result.get("result") == "exists":
            logger.info(f"⊙ Index already exists: {index_def['name']} in {db_name}")
        else:
            logger.info(f"✓ Index ready: {index_def['name']} in {db_name}")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to create index {index_def['name']} in {db_name}: {e}")
        return False


def create_articles_indexes() -> int:
    """
    Create indexes for articles collection.
    
    Returns:
        Number of successfully created indexes
    """
    logger.info("Creating indexes for articles collection...")
    
    indexes = [
        {
            "index": {
                "fields": ["published"]
            },
            "name": "idx_published",
            "type": "json"
        },
        {
            "index": {
                "fields": ["userspace", "published"]
            },
            "name": "idx_userspace_published",
            "type": "json"
        },
        {
            "index": {
                "fields": ["feed_url", "published"]
            },
            "name": "idx_feed_url_published",
            "type": "json"
        },
        {
            "index": {
                "fields": ["userspace", "feed_url", "published"]
            },
            "name": "idx_userspace_feed_published",
            "type": "json"
        },
    ]
    
    success_count = 0
    for index_def in indexes:
        if create_index("articles", index_def):
            success_count += 1
    
    return success_count


def create_issues_indexes() -> int:
    """
    Create indexes for issues collection.
    
    Returns:
        Number of successfully created indexes
    """
    logger.info("Creating indexes for issues collection...")
    
    indexes = [
        {
            "index": {
                "fields": ["longevity"]
            },
            "name": "idx_longevity",
            "type": "json"
        },
        {
            "index": {
                "fields": ["userspace", "longevity"]
            },
            "name": "idx_userspace_longevity",
            "type": "json"
        },
        {
            "index": {
                "fields": ["feed_urls"]
            },
            "name": "idx_feed_urls",
            "type": "json"
        },
    ]
    
    success_count = 0
    for index_def in indexes:
        if create_index("issues", index_def):
            success_count += 1
    
    return success_count


def create_feeds_indexes() -> int:
    """
    Create indexes for feeds collection.
    
    Returns:
        Number of successfully created indexes
    """
    logger.info("Creating indexes for feeds collection...")
    
    indexes = [
        {
            "index": {
                "fields": ["userspace"]
            },
            "name": "idx_userspace",
            "type": "json"
        },
        {
            "index": {
                "fields": ["url"]
            },
            "name": "idx_url",
            "type": "json"
        },
    ]
    
    success_count = 0
    for index_def in indexes:
        if create_index("feeds", index_def):
            success_count += 1
    
    return success_count


def initialize_all_indexes() -> None:
    """
    Create all indexes for Moirai collections.
    
    This is idempotent and safe to run multiple times.
    """
    logger.info("="* 60)
    logger.info("Initializing CouchDB indexes for Moirai...")
    logger.info("="* 60)
    
    total_created = 0
    
    try:
        total_created += create_articles_indexes()
        total_created += create_issues_indexes()
        total_created += create_feeds_indexes()
        
        logger.info("="* 60)
        logger.info(f"Index initialization complete. {total_created} indexes ready.")
        logger.info("="* 60)
        
    except Exception as e:
        logger.error(f"Error during index initialization: {e}")
        raise


if __name__ == "__main__":
    # Configure logging for direct execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    initialize_all_indexes()
