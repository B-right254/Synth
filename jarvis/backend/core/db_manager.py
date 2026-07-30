"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os

from ..models.database import Base


class DatabaseManager:
    """Manages SQLite database connections with WAL mode."""
    
    def __init__(self, database_path: str):
        """Initialize database connection.
        
        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = database_path
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
            echo=False  # Set to True for SQL debugging
        )
        
        # Enable WAL mode for concurrent reads
        with self.engine.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        # Session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    @contextmanager
    def get_session(self) -> Session:
        """Get a database session context manager.
        
        Yields:
            SQLAlchemy Session object
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def init_database(database_path: str) -> DatabaseManager:
    """Initialize the database and return manager instance.
    
    Args:
        database_path: Path to SQLite database file
        
    Returns:
        DatabaseManager instance
    """
    # Ensure directory exists
    db_dir = os.path.dirname(database_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, mode=0o700)  # User-only permissions
    
    return DatabaseManager(database_path)
