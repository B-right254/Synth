"""
Core Task Execution Loop for JARVIS.
Integrates model decisions, tool execution, and state management.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from backend.services.task_runner import TaskRunner
from backend.services.model_engine import ModelDecisionEngine, ModelDecisionError, DecisionType
from backend.services.skills_system import get_registry, SkillResult
from backend.tools.executor import ToolExecutor, ToolOutput
from backend.models.database import Task, TaskEvent
from backend.api.schemas import TaskState

logger = logging.getLogger(__name__)


class TaskExecutionLoop:
    """
    Main execution loop for processing tasks.
    
    This is the core intelligence loop that:
    1. Observes current task state
    2. Requests decision from LLM
    3. Executes the decided action (tool/skill)
    4. Verifies results
    5. Updates task state
    6. Repeats until completion or failure
    """
    
    MAX_ACTIONS_PER_TASK = 50
    MAX_REPAIR_ATTEMPTS = 2
    
    def __init__(
        self,
        db_session: Session,
        task_runner: TaskRunner,
        tool_executor: ToolExecutor
    ):
        self.db = db_session
        self.runner = task_runner
        self.tool_executor = tool_executor
        self.model_engine = ModelDecisionEngine(db_session, tool_executor)
        
    async def execute_task(self, task_id: str) -> None:
        """
        Execute a single task from start to completion.
        
        Args:
            task_id: ID of the task to execute
            
        Raises:
            Exception: If task execution fails critically
        """
        logger.info(f"Starting execution of task: {task_id}")
        
        repair_attempts = 0
        action_count = 0
        
        try:
            # Transition to running state
            task = await self.runner.transition_state(
                task_id=task_id,
                new_state=TaskState.RUNNING,
                event_type="task.execution_started",
                event_data={"started_at": datetime.utcnow().isoformat()}
            )
            
            while True:
                # Check action limit
                if action_count >= self.MAX_ACTIONS_PER_TASK:
                    await self._fail_task(
                        task_id,
                        code="ACTION_LIMIT_EXCEEDED",
                        message=f"Exceeded maximum {self.MAX_ACTIONS_PER_TASK} actions"
                    )
                    break
                
                # Get current task state
                task = await self.runner.get_task(task_id)
                if not task:
                    raise RuntimeError(f"Task {task_id} not found")
                
                # Check for cancellation
                if task.state == TaskState.CANCELLED.value:
                    logger.info(f"Task {task_id} was cancelled")
                    break
                
                # Get event history for context
                events = self._get_event_history(task_id)
                
                # Request decision from model
                try:
                    decision_type, params = await self.model_engine.make_decision(
                        task_id=task.id,
                        original_request=task.original_request,
                        normalized_goal=task.normalized_goal,
                        event_history=events,
                        current_state=task.state,
                        pending_question=task.pending_question,
                        repair_context=None  # Will be set if this is a repair
                    )
                    repair_attempts = 0  # Reset on successful decision
                    
                except ModelDecisionError as e:
                    repair_attempts += 1
                    logger.warning(f"Model decision error (attempt {repair_attempts}): {e.message}")
                    
                    if repair_attempts > self.MAX_REPAIR_ATTEMPTS:
                        await self._fail_task(
                            task_id,
                            code=e.code,
                            message=f"Model failed after {repair_attempts} repair attempts: {e.message}"
                        )
                        break
                    
                    # Try again with repair context
                    continue
                
                # Execute the decision
                action_count += 1
                success = await self._execute_decision(
                    task_id=task_id,
                    decision_type=decision_type,
                    params=params
                )
                
                if not success:
                    # Action failed - let model decide next step
                    logger.warning(f"Action failed for task {task_id}, continuing loop")
                
                # Check if task reached terminal state
                task = await self.runner.get_task(task_id)
                if task.state in [
                    TaskState.COMPLETED.value,
                    TaskState.FAILED.value,
                    TaskState.CANCELLED.value,
                    TaskState.WAITING_FOR_USER.value
                ]:
                    logger.info(f"Task {task_id} reached state: {task.state}")
                    if task.state != TaskState.WAITING_FOR_USER.value:
                        break
                    
        except Exception as e:
            logger.error(f"Critical error in task execution: {e}", exc_info=True)
            await self._fail_task(
                task_id,
                code="EXECUTION_ERROR",
                message=str(e)
            )
            raise
    
    def _get_event_history(self, task_id: str) -> List[Dict[str, Any]]:
        """Get event history for a task."""
        events = self.db.query(TaskEvent).filter_by(task_id=task_id).order_by(
            TaskEvent.sequence_num.asc()
        ).all()
        
        return [
            {
                "event_type": e.event_type,
                "event_data": json.loads(e.event_data) if e.event_data else {},
                "created_at": e.created_at.isoformat() if e.created_at else ""
            }
            for e in events
        ]
    
    async def _execute_decision(
        self,
        task_id: str,
        decision_type: str,
        params: Dict[str, Any]
    ) -> bool:
        """
        Execute a model decision.
        
        Args:
            task_id: Task ID
            decision_type: Type of decision
            params: Decision parameters
            
        Returns:
            True if execution was successful
        """
        logger.info(f"Executing decision: {decision_type} with params: {params}")
        
        try:
            if decision_type == DecisionType.COMPLETE_TASK:
                return await self._complete_task(task_id, params)
                
            elif decision_type == DecisionType.FAIL_TASK:
                return await self._fail_task_from_model(task_id, params)
                
            elif decision_type == DecisionType.REQUEST_USER_INPUT:
                return await self._request_user_input(task_id, params)
                
            elif decision_type == DecisionType.RUN_SKILL:
                return await self._run_skill(task_id, params)
                
            elif decision_type == DecisionType.EXECUTE_TOOL:
                return await self._execute_tool(task_id, params)
                
            else:
                logger.error(f"Unknown decision type: {decision_type}")
                return False
                
        except Exception as e:
            logger.error(f"Decision execution failed: {e}", exc_info=True)
            return False
    
    async def _complete_task(
        self,
        task_id: str,
        params: Dict[str, Any]
    ) -> bool:
        """Mark task as completed."""
        summary = params.get('summary', 'Task completed successfully')
        warnings = params.get('warnings', [])
        
        await self.runner.transition_state(
            task_id=task_id,
            new_state=TaskState.COMPLETED,
            event_type="task.completed",
            event_data={
                "summary": summary,
                "warnings": warnings,
                "completed_at": datetime.utcnow().isoformat()
            },
            final_result=summary
        )
        
        logger.info(f"Task {task_id} completed: {summary}")
        return True
    
    async def _fail_task_from_model(
        self,
        task_id: str,
        params: Dict[str, Any]
    ) -> bool:
        """Fail task based on model decision."""
        code = params.get('code', 'UNKNOWN_ERROR')
        user_message = params.get('user_message', 'Task failed')
        
        await self._fail_task(task_id, code, user_message)
        return True
    
    async def _fail_task(
        self,
        task_id: str,
        code: str,
        message: str
    ) -> bool:
        """Internal method to fail a task."""
        await self.runner.transition_state(
            task_id=task_id,
            new_state=TaskState.FAILED,
            event_type="task.failed",
            event_data={
                "code": code,
                "message": message,
                "failed_at": datetime.utcnow().isoformat()
            },
            terminal_reason=message
        )
        
        logger.warning(f"Task {task_id} failed: {code} - {message}")
        return False
    
    async def _request_user_input(
        self,
        task_id: str,
        params: Dict[str, Any]
    ) -> bool:
        """Request input from user."""
        question = params.get('question', 'I need more information')
        required_fields = params.get('required_fields', [])
        
        await self.runner.transition_state(
            task_id=task_id,
            new_state=TaskState.WAITING_FOR_USER,
            event_type="task.waiting_for_user",
            event_data={
                "question": question,
                "required_fields": required_fields,
                "waiting_since": datetime.utcnow().isoformat()
            },
            pending_question=question
        )
        
        logger.info(f"Task {task_id} waiting for user: {question}")
        return True
    
    async def _run_skill(
        self,
        task_id: str,
        params: Dict[str, Any]
    ) -> bool:
        """Execute a skill."""
        skill_id = params.get('skill_id')
        inputs = params.get('inputs', {})
        
        if not skill_id:
            logger.error("run_skill called without skill_id")
            return False
        
        registry = get_registry()
        skill = registry.get(skill_id)
        
        if not skill:
            logger.error(f"Skill not found: {skill_id}")
            return False
        
        # Execute skill
        result: SkillResult = await skill.execute(**inputs)
        
        # Record event
        await self.runner.transition_state(
            task_id=task_id,
            new_state=TaskState.RUNNING,  # Stay in running
            event_type="skill.executed",
            event_data={
                "skill_id": skill_id,
                "skill_name": skill.definition.name,
                "success": result.success,
                "output": str(result.output)[:500] if result.output else None,
                "error": result.error,
                "evidence": result.evidence,
                "duration_ms": result.duration_ms
            }
        )
        
        if result.success:
            logger.info(f"Skill {skill_id} executed successfully")
            return True
        else:
            logger.warning(f"Skill {skill_id} failed: {result.error}")
            return False
    
    async def _execute_tool(
        self,
        task_id: str,
        params: Dict[str, Any]
    ) -> bool:
        """Execute a tool."""
        tool_name = params.get('tool_name')
        tool_params = params.get('params', {})
        
        if not tool_name:
            logger.error("execute_tool called without tool_name")
            return False
        
        # Execute tool
        result: ToolOutput = await self.tool_executor.execute_tool(
            tool_name=tool_name,
            input_data=tool_params
        )
        
        # Record event
        await self.runner.transition_state(
            task_id=task_id,
            new_state=TaskState.RUNNING,  # Stay in running
            event_type="tool.executed",
            event_data={
                "tool_name": tool_name,
                "success": result.success,
                "output": result.data or result.output,
                "error": result.error,
                "evidence": result.evidence,
                "duration_ms": result.duration_ms
            }
        )
        
        if result.success:
            logger.info(f"Tool {tool_name} executed successfully")
            return True
        else:
            logger.warning(f"Tool {tool_name} failed: {result.error}")
            return False


async def run_task(db_session: Session, task_id: str, tool_executor: ToolExecutor) -> None:
    """
    Convenience function to run a single task.
    
    Args:
        db_session: Database session
        task_id: Task ID to execute
        tool_executor: Tool executor instance
    """
    runner = TaskRunner(db_session)
    
    # Acquire lease
    if not await runner.acquire_lease():
        raise RuntimeError("Another task runner is currently active")
    
    try:
        loop = TaskExecutionLoop(db_session, runner, tool_executor)
        await loop.execute_task(task_id)
    finally:
        await runner.release_lease()
