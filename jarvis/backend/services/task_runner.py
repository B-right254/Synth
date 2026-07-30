"""
Task runner service with state machine implementation.
Manages single task execution with durable state.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from backend.models.database import Task, TaskEvent, RunnerLease
from backend.api.schemas import TaskState


class TaskRunner:
    """Single task runner with lease management."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self._lease_nonce: Optional[str] = None
        self._current_task_id: Optional[str] = None

    async def acquire_lease(self, task_id: Optional[str] = None) -> bool:
        """Acquire exclusive runner lease.

        Args:
            task_id: Optional task ID being resumed
            
        Returns:
            True if lease acquired, False if another runner holds it
        """
        nonce = str(uuid.uuid4())
        
        # Check for existing lease
        existing = self.db.query(RunnerLease).filter_by(id=1).first()
        
        if existing:
            # Check if lease is stale (expired heartbeat - 30 second timeout)
            if datetime.utcnow() > existing.expires_at:
                # Stale lease detected - mark any running task as interrupted
                if existing.last_task_id:
                    self._mark_task_interrupted(existing.last_task_id)
                
                # Take over the lease
                existing.owner_nonce = nonce
                existing.process_id = id(self)
                existing.heartbeat = datetime.utcnow()
                existing.expires_at = datetime.utcnow() + timedelta(seconds=30)
                existing.last_task_id = task_id
                self.db.commit()
                self._lease_nonce = nonce
                self._current_task_id = task_id
                return True
            else:
                # Active lease held by another runner
                return False
        else:
            # No lease exists, create new one
            lease = RunnerLease(
                id=1,
                owner_nonce=nonce,
                process_id=id(self),
                heartbeat=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=30),
                last_task_id=task_id,
            )
            self.db.add(lease)
            self.db.commit()
            self._lease_nonce = nonce
            self._current_task_id = task_id
            return True

    async def renew_lease(self, task_id: Optional[str] = None) -> bool:
        """Renew the runner lease heartbeat.

        Args:
            task_id: Optional task ID to update
            
        Returns:
            True if renewal successful, False if lease lost
        """
        if not self._lease_nonce:
            return False

        lease = self.db.query(RunnerLease).filter_by(id=1).first()
        if not lease or lease.owner_nonce != self._lease_nonce:
            self._lease_nonce = None
            return False

        lease.heartbeat = datetime.utcnow()
        lease.expires_at = datetime.utcnow() + timedelta(seconds=30)
        if task_id:
            lease.last_task_id = task_id
            self._current_task_id = task_id
        self.db.commit()
        return True

    async def release_lease(self):
        """Release the runner lease."""
        if self._lease_nonce:
            lease = self.db.query(RunnerLease).filter_by(id=1).first()
            if lease and lease.owner_nonce == self._lease_nonce:
                # Clear last_task_id on clean release
                lease.last_task_id = None
                self.db.delete(lease)
                self.db.commit()
            self._lease_nonce = None
            self._current_task_id = None

    def _mark_task_interrupted(self, task_id: str):
        """Mark a running task as interrupted due to crash/restart.
        
        This is called when we detect a stale lease and need to mark
        the previously running task as interrupted.
        
        Args:
            task_id: ID of the task that was running
        """
        task = self.db.query(Task).filter_by(id=task_id).first()
        if task and task.state == TaskState.RUNNING.value:
            # Mark task as interrupted
            task.state = TaskState.INTERRUPTED.value
            task.version += 1
            task.updated_at = datetime.utcnow()
            
            # Get next sequence number
            last_event = self.db.query(TaskEvent).filter_by(task_id=task_id).order_by(
                TaskEvent.sequence_num.desc()
            ).first()
            next_seq = (last_event.sequence_num + 1) if last_event else 1
            
            # Append interruption event
            import json
            event = TaskEvent(
                task_id=task_id,
                event_type="task.interrupted",
                event_data=json.dumps({
                    "reason": "runner_crash_or_restart",
                    "detected_at": datetime.utcnow().isoformat(),
                    "note": "Task was running when runner lease expired. Resume will re-observe before continuing."
                }),
                sequence_num=next_seq,
                created_at=datetime.utcnow(),
            )
            self.db.add(event)
            self.db.commit()
            logger.info(f"Marked task {task_id} as interrupted due to stale lease")

    def _verify_lease(self) -> bool:
        """Verify we still hold the lease."""
        if not self._lease_nonce:
            return False
        
        lease = self.db.query(RunnerLease).filter_by(id=1).first()
        return lease and lease.owner_nonce == self._lease_nonce

    async def create_task(self, original_request: str, idempotency_key: Optional[str] = None) -> Task:
        """Create a new task.

        Args:
            original_request: User's natural language request
            idempotency_key: Optional key for deduplication

        Returns:
            Created Task object

        Raises:
            RuntimeError: If lease not held
        """
        if not self._verify_lease():
            raise RuntimeError("Runner lease not held")

        # Check idempotency
        if idempotency_key:
            existing = self.db.query(Task).filter(
                Task.original_request == original_request
            ).first()
            if existing:
                return existing

        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            original_request=original_request,
            state=TaskState.CREATED.value,
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(task)

        # Append creation event
        event = TaskEvent(
            task_id=task_id,
            event_type="task.created",
            event_data='{"original_request": "' + original_request.replace('"', '\\"') + '"}',
            sequence_num=1,
            created_at=datetime.utcnow(),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(task)

        return task

    async def transition_state(
        self,
        task_id: str,
        new_state: TaskState,
        event_type: str,
        event_data: Dict[str, Any],
        **updates
    ) -> Task:
        """Transition a task to a new state.

        Args:
            task_id: Task ID
            new_state: New state
            event_type: Event type for audit log
            event_data: Event data dictionary
            **updates: Additional field updates

        Returns:
            Updated Task object

        Raises:
            RuntimeError: If lease not held or task not found
        """
        if not self._verify_lease():
            raise RuntimeError("Runner lease not held")

        task = self.db.query(Task).filter_by(id=task_id).first()
        if not task:
            raise RuntimeError(f"Task {task_id} not found")

        # Update state
        old_state = task.state
        task.state = new_state.value
        task.version += 1
        task.updated_at = datetime.utcnow()

        # Apply additional updates
        for key, value in updates.items():
            setattr(task, key, value)

        # Get next sequence number
        last_event = self.db.query(TaskEvent).filter_by(task_id=task_id).order_by(
            TaskEvent.sequence_num.desc()
        ).first()
        next_seq = (last_event.sequence_num + 1) if last_event else 1

        # Append event
        import json
        event = TaskEvent(
            task_id=task_id,
            event_type=event_type,
            event_data=json.dumps(event_data),
            sequence_num=next_seq,
            created_at=datetime.utcnow(),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(task)

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.db.query(Task).filter_by(id=task_id).first()

    async def list_tasks(self, limit: int = 50) -> List[Task]:
        """List tasks ordered by creation date."""
        return self.db.query(Task).order_by(
            Task.created_at.desc()
        ).limit(limit).all()

    async def cancel_task(self, task_id: str) -> Task:
        """Cancel a running task.

        Args:
            task_id: Task ID

        Returns:
            Updated Task object
        """
        return await self.transition_state(
            task_id=task_id,
            new_state=TaskState.CANCELLED,
            event_type="task.cancelled",
            event_data={"reason": "user_requested"},
            terminal_reason="cancelled_by_user",
        )


# Singleton instance per process
_runner: Optional[TaskRunner] = None


def get_runner(db_session: Session) -> TaskRunner:
    """Get or create task runner instance."""
    global _runner
    if _runner is None:
        _runner = TaskRunner(db_session)
    return _runner
