"""
Database models and schema definitions for JARVIS.
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship, declarative_base, Session
from datetime import datetime
import os

Base = declarative_base()


# Database manager for dependency injection
_db_manager = None


def get_db() -> Session:
    """Get database session for dependency injection.
    
    This function is used by FastAPI's Depends() to provide database sessions.
    It requires the database manager to be initialized first.
    """
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database first.")
    
    with _db_manager.get_session() as session:
        yield session


def set_db_manager(manager):
    """Set the database manager instance."""
    global _db_manager
    _db_manager = manager


class Task(Base):
    """Current state projection for a task."""
    
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    original_request = Column(Text, nullable=False)
    normalized_goal = Column(Text)
    state = Column(String, nullable=False)
    version = Column(Integer, default=1)
    active_action_id = Column(String)
    selected_skill_version = Column(String)
    pending_question = Column(Text)
    final_result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    terminal_reason = Column(String)
    
    # Events relationship
    events = relationship("TaskEvent", back_populates="task", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint(
            "state IN ('created', 'running', 'waiting_for_user', 'completed', 'failed', 'cancelled', 'interrupted')",
            name="check_task_state"
        ),
    )


class TaskEvent(Base):
    """Immutable audit log for task events."""
    
    __tablename__ = "task_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    event_type = Column(String, nullable=False)
    event_data = Column(Text, nullable=False)
    sequence_num = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    task = relationship("Task", back_populates="events")


class RunnerLease(Base):
    """Single instance enforcement lease."""
    
    __tablename__ = "runner_lease"
    
    id = Column(Integer, primary_key=True)
    owner_nonce = Column(String, nullable=False)
    process_id = Column(Integer, nullable=False)
    heartbeat = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint("id = 1", name="check_single_lease"),
    )


class Skill(Base):
    """Declarative skill definition."""
    
    __tablename__ = "skills"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    state = Column(String, default="enabled")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Versions relationship
    versions = relationship("SkillVersion", back_populates="skill", cascade="all, delete-orphan")


class SkillVersion(Base):
    """Versioned skill definitions."""
    
    __tablename__ = "skill_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_id = Column(String, ForeignKey("skills.id"), nullable=False)
    version = Column(String, nullable=False)
    definition = Column(Text, nullable=False)
    validation_result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    skill = relationship("Skill", back_populates="versions")


class SettingsMetadata(Base):
    """Non-secret settings storage."""
    
    __tablename__ = "settings_metadata"
    
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
