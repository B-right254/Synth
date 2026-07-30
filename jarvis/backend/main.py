"""
FastAPI application for JARVIS backend.
"""

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import uuid

from .core.config import settings, generate_control_token
from .core.db_manager import init_database, DatabaseManager
from .core.auth import create_auth_dependency
from .api.schemas import HealthResponse, ErrorResponse
from .tools.executor import ToolExecutor
from .tools.system_tools import create_system_tools


# Global instances
db_manager: DatabaseManager = None
tool_executor: ToolExecutor = None
control_token: str = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_manager, tool_executor, control_token
    
    # Startup
    control_token = generate_control_token()
    print(f"JARVIS starting with control token: {control_token[:8]}...")
    
    # Initialize database
    db_path = settings.database_path or os.path.join(
        os.path.expanduser("~"),
        ".jarvis",
        "jarvis.db"
    )
    db_manager = init_database(db_path)
    print(f"Database initialized at: {db_path}")
    
    # Initialize tool executor
    tool_executor = ToolExecutor()
    
    # Register system tools
    for tool in create_system_tools():
        tool_executor.register_tool(tool)
    print(f"Registered {len(tool_executor.list_tools())} tools")
    
    yield
    
    # Shutdown
    print("JARVIS shutting down...")


app = FastAPI(
    title="JARVIS Backend",
    description="Windows 10/11 Personal Desktop Assistant API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware - only allow local origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_auth():
    """Get authentication dependency."""
    return create_auth_dependency(control_token)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        database_connected=db_manager is not None,
        cloud_configured=bool(settings.ollama_api_key)
    )


@app.post("/tasks")
async def create_task(request: Request, auth: bool = Depends(get_auth())):
    """Create a new task."""
    # TODO: Implement task creation
    return {"message": "Task creation not yet implemented"}


@app.get("/tasks")
async def list_tasks(auth: bool = Depends(get_auth())):
    """List all tasks."""
    # TODO: Implement task listing
    return {"tasks": [], "total": 0}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str, auth: bool = Depends(get_auth())):
    """Get a specific task."""
    # TODO: Implement task retrieval
    return {"message": f"Task {task_id} not found"}


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, auth: bool = Depends(get_auth())):
    """Cancel a running task."""
    # TODO: Implement task cancellation
    return {"message": "Task cancellation not yet implemented"}


@app.get("/settings")
async def get_settings(auth: bool = Depends(get_auth())):
    """Get current settings."""
    # TODO: Implement settings retrieval
    return {"settings": {}}


@app.put("/settings")
async def update_settings(request: Request, auth: bool = Depends(get_auth())):
    """Update settings."""
    # TODO: Implement settings update
    return {"message": "Settings update not yet implemented"}


@app.get("/tools")
async def list_tools(auth: bool = Depends(get_auth())):
    """List available tools."""
    if tool_executor:
        return {"tools": tool_executor.list_tools()}
    return {"tools": []}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    return ErrorResponse(
        error="INTERNAL_ERROR",
        detail=str(exc),
        code="500"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
