"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskState(str, Enum):
    """Valid task states."""
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


# Task Schemas

class TaskCreate(BaseModel):
    """Schema for creating a new task."""
    original_request: str = Field(..., min_length=1, max_length=10000)
    idempotency_key: Optional[str] = None


class TaskReply(BaseModel):
    """Schema for replying to a waiting_for_user task."""
    answer: str = Field(..., min_length=1, max_length=5000)


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: str
    original_request: str
    normalized_goal: Optional[str]
    state: TaskState
    version: int
    active_action_id: Optional[str]
    pending_question: Optional[str]
    final_result: Optional[str]
    created_at: datetime
    updated_at: datetime
    terminal_reason: Optional[str]
    
    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Schema for listing tasks."""
    tasks: List[TaskResponse]
    total: int


# Event Schemas

class TaskEventResponse(BaseModel):
    """Schema for task event response."""
    id: int
    task_id: str
    event_type: str
    event_data: Dict[str, Any]
    sequence_num: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Tool Execution Schemas

class ToolInput(BaseModel):
    """Base schema for tool input."""
    pass


class ToolOutput(BaseModel):
    """Schema for tool execution output."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    duration_ms: int


# System Read Tool Schemas

class SystemTimeInput(ToolInput):
    """Input for system time tool."""
    pass


class SystemBatteryInput(ToolInput):
    """Input for battery status tool."""
    pass


class SystemDiskInput(ToolInput):
    """Input for disk space tool."""
    path: Optional[str] = None


class SystemProcessesInput(ToolInput):
    """Input for process list tool."""
    limit: int = Field(default=50, ge=1, le=200)


class SystemActiveWindowInput(ToolInput):
    """Input for active window tool."""
    pass


# File Tool Schemas

class FileListInput(ToolInput):
    """Input for listing directory contents."""
    path: str
    include_hidden: bool = False


class FileReadInput(ToolInput):
    """Input for reading a file."""
    path: str
    max_bytes: int = Field(default=1048576, ge=1, le=10485760)  # Default 1MB, max 10MB


class FileCreateInput(ToolInput):
    """Input for creating a file."""
    path: str
    content: str
    overwrite: bool = False


class FileWriteInput(ToolInput):
    """Input for writing to a file."""
    path: str
    content: str
    append: bool = False


class FileMoveInput(ToolInput):
    """Input for moving a file."""
    source_path: str
    destination_path: str
    overwrite: bool = False


class FileCopyInput(ToolInput):
    """Input for copying a file."""
    source_path: str
    destination_path: str
    overwrite: bool = False


class FileDeleteInput(ToolInput):
    """Input for deleting a file."""
    path: str
    use_recycle_bin: bool = True


# Application Tool Schemas

class AppListInput(ToolInput):
    """Input for listing installed applications."""
    search_term: Optional[str] = None


class AppLaunchInput(ToolInput):
    """Input for launching an application."""
    app_id: str


class AppFocusInput(ToolInput):
    """Input for focusing an application window."""
    app_id: str


class AppCloseInput(ToolInput):
    """Input for closing an application."""
    app_id: str
    force: bool = False


# Package Tool Schemas

class PackageSearchInput(ToolInput):
    """Input for searching packages."""
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class PackageListInput(ToolInput):
    """Input for listing installed packages."""
    search_term: Optional[str] = None


class PackageInstallInput(ToolInput):
    """Input for installing a package."""
    package_id: str
    source: Optional[str] = None


class PackageUninstallInput(ToolInput):
    """Input for uninstalling a package."""
    package_id: str


# GUI Tool Schemas

class GUIObserveInput(ToolInput):
    """Input for GUI observation."""
    window_title: Optional[str] = None
    element_description: Optional[str] = None
    use_ocr: bool = False


class GUIFocusInput(ToolInput):
    """Input for focusing a window."""
    window_title: str


class GUIInvokeInput(ToolInput):
    """Input for invoking a UI element."""
    window_title: str
    element_description: str


class GUISetValueInput(ToolInput):
    """Input for setting a UI element value."""
    window_title: str
    element_description: str
    value: str


class GUIClickInput(ToolInput):
    """Input for coordinate click."""
    window_title: str
    x: int
    y: int


class GUITypeInput(ToolInput):
    """Input for keyboard input."""
    window_title: str
    text: str


class GUIHotkeyInput(ToolInput):
    """Input for hotkey execution."""
    window_title: str
    keys: List[str]


# Control Tool Schemas

class CancelTaskInput(ToolInput):
    """Input for cancelling current task."""
    task_id: str


# Model Decision Schemas

class ModelDecisionCompleteTask(BaseModel):
    """Schema for complete_task model decision."""
    summary: str
    warnings: Optional[List[str]] = None


class ModelDecisionFailTask(BaseModel):
    """Schema for fail_task model decision."""
    code: str
    user_message: str


class ModelDecisionRequestUserInput(BaseModel):
    """Schema for request_user_input model decision."""
    question: str
    required_fields: Optional[List[str]] = None


class ModelDecisionRunSkill(BaseModel):
    """Schema for run_skill model decision."""
    skill_id: str
    inputs: Dict[str, Any]


# Settings Schemas

class SettingsUpdate(BaseModel):
    """Schema for updating settings."""
    key: str
    value: str


class SettingsResponse(BaseModel):
    """Schema for settings response."""
    settings: Dict[str, str]


# Health Check Schemas

class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    version: str
    database_connected: bool
    cloud_configured: bool


# Voice Schemas

class VoiceStartResponse(BaseModel):
    """Schema for voice session start response."""
    session_id: str
    status: str


class VoiceAudioInput(BaseModel):
    """Schema for voice audio frame."""
    session_id: str
    audio_data: str  # Base64 encoded PCM
    sample_rate: int = 16000
    channels: int = 1


# Error Response Schema

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
