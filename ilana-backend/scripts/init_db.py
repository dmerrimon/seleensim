#!/usr/bin/env python3
"""
Database Initialization Script for Ilana Seat Management

Run this script to create the database tables:
    python scripts/init_db.py

Prerequisites:
    - DATABASE_URL environment variable must be set
    - PostgreSQL database must be accessible

Example DATABASE_URL formats:
    postgresql://user:password@host:5432/ilana
    postgres://user:password@host:5432/ilana  (Render format)
"""

import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Initialize the database"""

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        logger.info("")
        logger.info("Please set DATABASE_URL to your PostgreSQL connection string:")
        logger.info("  export DATABASE_URL=postgresql://user:password@host:5432/ilana")
        logger.info("")
        logger.info("Or create a .env file with:")
        logger.info("  DATABASE_URL=postgresql://user:password@host:5432/ilana")
        sys.exit(1)

    # Mask password in log output
    masked_url = database_url
    if "@" in masked_url:
        parts = masked_url.split("@")
        if ":" in parts[0]:
            prefix = parts[0].rsplit(":", 1)[0]
            masked_url = f"{prefix}:****@{parts[1]}"

    logger.info(f"Connecting to: {masked_url}")

    try:
        from database import init_database, Base, engine

        # Initialize database (creates tables)
        success = init_database()

        if success:
            logger.info("")
            logger.info("=" * 50)
            logger.info("DATABASE INITIALIZATION SUCCESSFUL")
            logger.info("=" * 50)
            logger.info("")
            logger.info("Created tables:")
            for table in Base.metadata.tables:
                logger.info(f"  - {table}")
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Set AZURE_CLIENT_ID for Microsoft SSO")
            logger.info("  2. Deploy to Render or run locally")
            logger.info("  3. First user to sign in becomes admin")
            logger.info("")
        else:
            logger.error("Database initialization failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def check_tables():
    """Check existing tables in the database"""
    from database import init_database, engine
    from sqlalchemy import inspect

    init_database()

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    logger.info("Existing tables:")
    for table in tables:
        logger.info(f"  - {table}")
        columns = inspector.get_columns(table)
        for col in columns:
            logger.info(f"      {col['name']}: {col['type']}")


def drop_tables():
    """Drop all tables (use with caution!)"""
    from database import init_database, Base, engine

    confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
    if confirm.lower() != 'yes':
        logger.info("Aborted")
        return

    init_database()
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            check_tables()
        elif sys.argv[1] == "drop":
            drop_tables()
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Usage: python scripts/init_db.py [check|drop]")
    else:
        main()
