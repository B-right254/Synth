"""
Model Decision Engine for JARVIS.
Handles LLM orchestration, context building, and decision parsing.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from backend.adapters.ollama_adapter import get_adapter, format_tools_for_ollama
from backend.tools.executor import ToolExecutor
from backend.services.skills_system import get_registry
from backend.api.schemas import TaskState

logger = logging.getLogger(__name__)


class ModelDecisionError(Exception):
    """Raised when model decision is invalid or cannot be parsed."""
    def __init__(self, code: str, message: str, attempt: int = 0):
        self.code = code
        self.message = message
        self.attempt = attempt
        super().__init__(message)


class DecisionType:
    """Valid model decision types."""
    COMPLETE_TASK = "complete_task"
    FAIL_TASK = "fail_task"
    REQUEST_USER_INPUT = "request_user_input"
    RUN_SKILL = "run_skill"
    EXECUTE_TOOL = "execute_tool"


class ModelDecisionEngine:
    """
    Core LLM orchestration engine.
    
    Responsibilities:
    - Build context from task state, history, and available tools
    - Send requests to Ollama Cloud with tool definitions
    - Parse and validate model decisions
    - Handle repair attempts (max 2)
    - Track token usage
    """
    
    MAX_REPAIR_ATTEMPTS = 2
    MAX_TOKENS_PER_REQUEST = 4000
    MAX_TOKENS_PER_TASK = 50000
    
    def __init__(self, db_session: Session, tool_executor: ToolExecutor):
        self.db = db_session
        self.tool_executor = tool_executor
        self.adapter = get_adapter()
        self.token_count = 0
        self.decision_history: List[Dict[str, Any]] = []
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt for JARVIS behavior."""
        return """You are JARVIS, a Windows 10/11 personal desktop assistant.

Your role is to help users accomplish tasks on their Windows computer through safe, verified actions.

IMPORTANT RULES:
1. You can only make ONE decision at a time - never parallel calls
2. Always observe state before taking actions
3. Verify after every mutating operation
4. Respect user privacy - never access files outside approved roots
5. Do not automate browsers or execute arbitrary shell commands
6. Handle errors gracefully with honest failure messages
7. Ask for clarification when targets are ambiguous
8. Stop immediately if the user cancels

AVAILABLE TOOLS:
- System reads: get_time, get_battery_status, get_disk_usage, list_processes, get_active_window
- File operations: list_directory, read_file, create_file, write_file, move_file, copy_file, delete_file
- Application control: list_apps, launch_app, focus_app, close_app
- Package management: search_packages, list_packages, install_package, uninstall_package
- GUI interaction: observe_gui, focus_window, invoke_element, set_value, click, type_text, send_hotkey
- Skills: run_skill (for complex multi-step workflows)

DECISION TYPES:
1. complete_task - When the task is fully accomplished
2. fail_task - When you cannot complete the task (after max 2 repair attempts)
3. request_user_input - When you need clarification or user confirmation
4. run_skill - To execute a registered skill workflow
5. execute_tool - To call a single tool with specific parameters

Always think step-by-step and prefer observation before action."""

    def _build_context(
        self,
        task_id: str,
        original_request: str,
        normalized_goal: Optional[str],
        event_history: List[Dict[str, Any]],
        current_state: str,
        pending_question: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Build conversation context for the model.
        
        Args:
            task_id: Current task ID
            original_request: User's original request
            normalized_goal: Normalized task goal if available
            event_history: List of past events
            current_state: Current task state
            pending_question: Question awaiting user response
            
        Returns:
            List of message dicts for the API
        """
        messages = []
        
        # System prompt
        messages.append({
            "role": "system",
            "content": self._build_system_prompt()
        })
        
        # User request
        user_content = f"Task ID: {task_id}\n"
        user_content += f"Original Request: {original_request}\n"
        
        if normalized_goal:
            user_content += f"Normalized Goal: {normalized_goal}\n"
            
        if pending_question:
            user_content += f"\nPENDING QUESTION (awaiting your next action after user response): {pending_question}\n"
        
        # Add recent event history (last 10 events)
        if event_history:
            recent_events = event_history[-10:]
            user_content += "\nRecent Activity:\n"
            for event in recent_events:
                event_type = event.get('event_type', 'unknown')
                event_data = event.get('event_data', {})
                timestamp = event.get('created_at', '')
                
                if event_type == 'tool.executed':
                    tool_name = event_data.get('tool_name', 'unknown')
                    success = event_data.get('success', False)
                    result_summary = str(event_data.get('output', {}))[:200]
                    user_content += f"- [{timestamp}] Tool '{tool_name}' executed: {'SUCCESS' if success else 'FAILED'}\n"
                    user_content += f"  Result: {result_summary}\n"
                elif event_type == 'skill.executed':
                    skill_name = event_data.get('skill_name', 'unknown')
                    success = event_data.get('success', False)
                    user_content += f"- [{timestamp}] Skill '{skill_name}' executed: {'SUCCESS' if success else 'FAILED'}\n"
                elif event_type == 'user.replied':
                    answer = event_data.get('answer', '')
                    user_content += f"- [{timestamp}] User replied: {answer}\n"
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    def _parse_decision(self, response: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Parse model response into decision type and parameters.
        
        Args:
            response: Raw API response from Ollama Cloud
            
        Returns:
            Tuple of (decision_type, decision_params)
            
        Raises:
            ModelDecisionError: If response is invalid
        """
        try:
            # Check for tool calls in response
            choices = response.get('choices', [])
            if not choices:
                raise ModelDecisionError(
                    code="EMPTY_RESPONSE",
                    message="Model returned no choices"
                )
            
            message = choices[0].get('message', {})
            tool_calls = message.get('tool_calls', [])
            
            if not tool_calls:
                # Model didn't use tools - might be thinking or confused
                content = message.get('content', '')
                if content:
                    # Try to infer intent from content
                    logger.warning(f"Model returned text instead of tool call: {content[:200]}")
                    raise ModelDecisionError(
                        code="NO_TOOL_CALL",
                        message="Model must use tool calls for decisions"
                    )
                else:
                    raise ModelDecisionError(
                        code="EMPTY_MESSAGE",
                        message="Model returned empty response"
                    )
            
            # We expect exactly ONE tool call
            if len(tool_calls) > 1:
                raise ModelDecisionError(
                    code="PARALLEL_CALLS",
                    message="Model made multiple parallel calls - only one allowed"
                )
            
            tool_call = tool_calls[0]
            function = tool_call.get('function', {})
            decision_type = function.get('name', '')
            
            # Validate decision type
            valid_types = [
                DecisionType.COMPLETE_TASK,
                DecisionType.FAIL_TASK,
                DecisionType.REQUEST_USER_INPUT,
                DecisionType.RUN_SKILL,
                DecisionType.EXECUTE_TOOL
            ]
            
            if decision_type not in valid_types:
                raise ModelDecisionError(
                    code="INVALID_DECISION_TYPE",
                    message=f"Unknown decision type: {decision_type}"
                )
            
            # Parse arguments
            try:
                args = json.loads(function.get('arguments', '{}'))
            except json.JSONDecodeError as e:
                raise ModelDecisionError(
                    code="INVALID_JSON",
                    message=f"Failed to parse arguments: {str(e)}"
                )
            
            return decision_type, args
            
        except ModelDecisionError:
            raise
        except Exception as e:
            raise ModelDecisionError(
                code="PARSE_ERROR",
                message=f"Failed to parse response: {str(e)}"
            )
    
    async def make_decision(
        self,
        task_id: str,
        original_request: str,
        normalized_goal: Optional[str],
        event_history: List[Dict[str, Any]],
        current_state: str,
        pending_question: Optional[str] = None,
        repair_context: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Make a decision for the current task state.
        
        Args:
            task_id: Task ID
            original_request: User's original request
            normalized_goal: Normalized goal
            event_history: Event history
            current_state: Current state
            pending_question: Pending question if any
            repair_context: Error context for repair attempts
            
        Returns:
            Tuple of (decision_type, decision_params)
            
        Raises:
            ModelDecisionError: If decision cannot be made
        """
        # Build context
        messages = self._build_context(
            task_id=task_id,
            original_request=original_request,
            normalized_goal=normalized_goal,
            event_history=event_history,
            current_state=current_state,
            pending_question=pending_question
        )
        
        # Add repair context if this is a repair attempt
        if repair_context:
            messages.append({
                "role": "user",
                "content": f"REPAIR REQUIRED: {repair_context}\n\nPlease provide a valid decision."
            })
        
        # Get tools for the model
        tools = self.tool_executor.list_tools()
        formatted_tools = format_tools_for_ollama(tools)
        
        # Add skills as callable tools
        registry = get_registry()
        skills = registry.list_skills()
        # Skills are called via run_skill decision type, not as separate tools
        
        try:
            # Call Ollama Cloud
            response = await self.adapter.execute_tool_call(
                messages=messages,
                tools=formatted_tools,
                max_tokens=self.MAX_TOKENS_PER_REQUEST
            )
            
            # Track tokens (estimate)
            usage = response.get('usage', {})
            tokens_used = usage.get('total_tokens', 0)
            self.token_count += tokens_used
            
            if self.token_count > self.MAX_TOKENS_PER_TASK:
                logger.warning(f"Token budget exceeded for task: {self.token_count}")
            
            # Parse decision
            decision_type, params = self._parse_decision(response)
            
            # Store in history
            self.decision_history.append({
                'type': decision_type,
                'params': params,
                'timestamp': datetime.utcnow().isoformat(),
                'tokens': tokens_used
            })
            
            logger.info(f"Model decision: {decision_type}")
            return decision_type, params
            
        except ModelDecisionError:
            raise
        except Exception as e:
            logger.error(f"Model request failed: {e}")
            raise ModelDecisionError(
                code="CLOUD_ERROR",
                message=f"Ollama Cloud request failed: {str(e)}"
            )
    
    def get_token_usage(self) -> int:
        """Get total tokens used for this task."""
        return self.token_count
    
    def get_decision_history(self) -> List[Dict[str, Any]]:
        """Get decision history for this task."""
        return self.decision_history.copy()
