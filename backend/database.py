"""
Database configuration and setup
SQLAlchemy ORM configuration, session management
"""

import os
import logging
from pathlib import Path

# Load environment variables from .env file (if it exists)
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not installed, use system environment

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/linkedin_generator_dev"
)

# For SQLite in development (uncomment to use)
# DATABASE_URL = "sqlite:///./linkedin_generator.db"
# SQLALCHEMY_KWARGS = {"connect_args": {"check_same_thread": False}}

# Engine configuration
SQLALCHEMY_KWARGS = {}

if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL specific optimizations
    SQLALCHEMY_KWARGS = {
        "poolclass": QueuePool,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,  # Test connections before use
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "echo": os.getenv("SQL_ECHO", "false").lower() == "true"
    }
else:
    # SQLite for development
    SQLALCHEMY_KWARGS = {
        "connect_args": {"check_same_thread": False}
    }

# Create engine
engine = create_engine(
    DATABASE_URL,
    **SQLALCHEMY_KWARGS
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Session:
    """Get database session (for FastAPI dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    from backend.models import Base
    
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete")


def drop_db():
    """Drop all tables (WARNING: destroys data)"""
    from backend.models import Base
    
    logger.warning("DROPPING ALL DATABASE TABLES!")
    Base.metadata.drop_all(bind=engine)
    logger.warning("Database dropped")


def reset_db():
    """Reset database (drop and recreate all tables)"""
    logger.warning("RESETTING DATABASE!")
    drop_db()
    init_db()
    logger.info("Database reset complete")


# Context manager for database sessions
class Database:
    """Database connection manager"""
    
    @staticmethod
    def get_session() -> Session:
        """Get a new database session"""
        return SessionLocal()
    
    @staticmethod
    def execute_in_transaction(func):
        """Execute function in database transaction"""
        db = SessionLocal()
        try:
            result = func(db)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            db.close()


# Event listeners for connection pool
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better performance"""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Health check
def is_database_healthy() -> bool:
    """Check if database is accessible"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
