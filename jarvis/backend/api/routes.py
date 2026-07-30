"""
API Routes for JARVIS Backend
Handles task management, tool execution, settings, and skills.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.services.task_runner import get_runner, TaskRunner
from backend.services.skills_system import get_registry, initialize_default_skills
from backend.adapters.ollama_adapter import get_adapter, format_tools_for_ollama
from backend.tools.executor import ToolExecutor
from backend.api.schemas import (
    TaskCreate, TaskResponse, TaskListResponse, 
    TaskState, HealthResponse, SettingsResponse,
    ToolExecutionRequest, ToolExecutionResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_tool_executor() -> ToolExecutor:
    """Get or create tool executor instance."""
    if not hasattr(get_tool_executor, '_executor'):
        get_tool_executor._executor = ToolExecutor()
        # Register all tools
        from backend.tools.system_tools import create_system_tools
        from backend.tools.file_tools import create_file_tools
        from backend.tools.app_tools import create_app_tools
        from backend.tools.package_tools import create_package_tools
        
        for tool in create_system_tools():
            get_tool_executor._executor.register_tool(tool)
        for tool in create_file_tools():
            get_tool_executor._executor.register_tool(tool)
        for tool in create_app_tools():
            get_tool_executor._executor.register_tool(tool)
        for tool in create_package_tools():
            get_tool_executor._executor.register_tool(tool)
            
    return get_tool_executor._executor


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Check system health status."""
    from core.config import settings
    
    # Check Ollama Cloud connectivity
    adapter = get_adapter()
    cloud_ok = await adapter.check_health() if adapter else False
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        database_connected=True,
        cloud_configured=cloud_ok
    )


@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    tool_executor: ToolExecutor = Depends(get_tool_executor)
):
    """Create a new task from user request."""
    runner = get_runner(db)
    
    # Acquire lease
    if not await runner.acquire_lease():
        raise HTTPException(
            status_code=409,
            detail="Another task runner is currently active"
        )
    
    try:
        # Create task
        task = await runner.create_task(
            original_request=task_data.original_request,
            idempotency_key=task_data.idempotency_key
        )
        
        # Initialize skills registry if not done
        registry = get_registry()
        if len(registry.list_skills()) == 0:
            initialize_default_skills()
        
        # Get available tools for LLM
        tools = tool_executor.list_tools()
        formatted_tools = format_tools_for_ollama(tools)
        
        # Transition to planning state
        await runner.transition_state(
            task_id=task.id,
            new_state=TaskState.PLANNING,
            event_type="task.planning_started",
            event_data={
                "tools_available": len(tools),
                "skills_available": len(registry.list_skills())
            }
        )
        
        return TaskResponse(
            id=task.id,
            original_request=task.original_request,
            state=TaskState(task.state),
            created_at=task.created_at,
            updated_at=task.updated_at,
            version=task.version
        )
        
    finally:
        # Release lease after task creation
        await runner.release_lease()


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    limit: int = 50,
    state: Optional[TaskState] = None,
    db: Session = Depends(get_db)
):
    """List tasks with optional filtering."""
    runner = get_runner(db)
    
    if state:
        # Filter by state - would need to add filtering to runner
        tasks = await runner.list_tasks(limit=limit)
        tasks = [t for t in tasks if t.state == state.value]
    else:
        tasks = await runner.list_tasks(limit=limit)
    
    return TaskListResponse(
        tasks=[
            TaskResponse(
                id=t.id,
                original_request=t.original_request,
                state=TaskState(t.state),
                created_at=t.created_at,
                updated_at=t.updated_at,
                version=t.version
            )
            for t in tasks
        ],
        total=len(tasks)
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    """Get a specific task by ID."""
    runner = get_runner(db)
    task = await runner.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return TaskResponse(
        id=task.id,
        original_request=task.original_request,
        state=TaskState(task.state),
        created_at=task.created_at,
        updated_at=task.updated_at,
        version=task.version
    )


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """Cancel a running task."""
    runner = get_runner(db)
    
    # Acquire lease
    if not await runner.acquire_lease():
        raise HTTPException(
            status_code=409,
            detail="Cannot cancel task while another runner is active"
        )
    
    try:
        task = await runner.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Check if task can be cancelled
        if task.state in [TaskState.COMPLETED.value, TaskState.FAILED.value, TaskState.CANCELLED.value]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel task in state {task.state}"
            )
        
        updated_task = await runner.cancel_task(task_id)
        
        return TaskResponse(
            id=updated_task.id,
            original_request=updated_task.original_request,
            state=TaskState(updated_task.state),
            created_at=updated_task.created_at,
            updated_at=updated_task.updated_at,
            version=updated_task.version
        )
        
    finally:
        await runner.release_lease()


@router.get("/tasks/{task_id}/events")
async def get_task_events(task_id: str, db: Session = Depends(get_db)):
    """Get event history for a task."""
    from backend.models.database import TaskEvent
    
    events = db.query(TaskEvent).filter_by(task_id=task_id).order_by(
        TaskEvent.sequence_num.asc()
    ).all()
    
    return {
        "task_id": task_id,
        "events": [
            {
                "event_type": e.event_type,
                "event_data": e.event_data,
                "sequence_num": e.sequence_num,
                "created_at": e.created_at
            }
            for e in events
        ]
    }


@router.post("/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    request: ToolExecutionRequest,
    tool_executor: ToolExecutor = Depends(get_tool_executor)
):
    """Execute a tool directly (for testing/manual execution)."""
    try:
        result = await tool_executor.execute_tool(
            tool_name=request.tool_name,
            params=request.params
        )
        
        return ToolExecutionResponse(
            success=result.success,
            output=result.output,
            error=result.error,
            evidence=result.evidence
        )
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return ToolExecutionResponse(
            success=False,
            output=None,
            error=str(e),
            evidence=None
        )


@router.get("/tools", response_model=Dict[str, List[Dict[str, Any]]])
async def list_tools(tool_executor: ToolExecutor = Depends(get_tool_executor)):
    """List all available tools."""
    tools = tool_executor.list_tools()
    return {"tools": tools}


@router.get("/skills", response_model=List[Dict[str, Any]])
async def list_skills(category: Optional[str] = None):
    """List all available skills."""
    registry = get_registry()
    
    # Initialize if empty
    if len(registry.list_skills()) == 0:
        initialize_default_skills()
    
    if category:
        from backend.services.skills_system import SkillCategory
        try:
            cat = SkillCategory(category)
            skills = registry.list_skills(category=cat)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    else:
        skills = registry.list_skills()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "category": s.category.value,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default
                }
                for p in s.parameters
            ],
            "risk_level": s.risk_level,
            "requires_confirmation": s.requires_confirmation
        }
        for s in skills
    ]


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    """Get a specific skill definition."""
    registry = get_registry()
    skill = registry.get(skill_id)
    
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    
    d = skill.definition
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "category": d.category.value,
        "parameters": [
            {
                "name": p.name,
                "type": p.type,
                "description": p.description,
                "required": p.required,
                "default": p.default,
                "enum": p.enum
            }
            for p in d.parameters
        ],
        "returns": d.returns,
        "examples": d.examples,
        "risk_level": d.risk_level,
        "requires_confirmation": d.requires_confirmation
    }


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current application settings."""
    from backend.core.config import settings
    
    return SettingsResponse(
        host=settings.host,
        port=settings.port,
        ollama_cloud_base_url=settings.ollama_cloud_base_url,
        selected_model=settings.selected_model,
        file_roots=settings.file_roots,
        max_actions_per_task=settings.max_actions_per_task,
        max_cloud_requests_per_task=settings.max_cloud_requests_per_task,
        voice_enabled=settings.voice_enabled
    )


@router.put("/settings")
async def update_settings(request: Request):
    """Update application settings."""
    # Note: In production, settings should be persisted to a config file
    # For now, this is a stub that acknowledges the request
    data = await request.json()
    
    # Validate and update settings would go here
    # For security, most settings should only be configurable via Tauri frontend
    
    return {
        "message": "Settings update acknowledged",
        "updated_keys": list(data.keys()),
        "note": "Some settings require application restart"
    }


@router.get("/models")
async def list_models():
    """List available Ollama Cloud models."""
    adapter = get_adapter()
    
    try:
        models = await adapter.list_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to fetch models: {str(e)}")


@router.post("/chat/completions")
async def chat_completion(request: Request):
    """Send a chat completion request to Ollama Cloud."""
    adapter = get_adapter()
    data = await request.json()
    
    messages = data.get("messages", [])
    tools = data.get("tools", [])
    
    if not messages:
        raise HTTPException(status_code=400, detail="Messages are required")
    
    try:
        # Format tools if provided
        formatted_tools = format_tools_for_ollama(tools) if tools else []
        
        response = await adapter.execute_tool_call(
            messages=messages,
            tools=formatted_tools,
            max_tokens=data.get("max_tokens", 4000)
        )
        
        return response
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=502, detail=f"Ollama Cloud request failed: {str(e)}")
