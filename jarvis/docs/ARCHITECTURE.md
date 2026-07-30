# JARVIS Architecture Decision Record

## Overview
This document captures the architectural decisions for the JARVIS Windows 10/11 personal desktop assistant.

## System Architecture

### Core Components

1. **Frontend (React + Tauri)**
   - Desktop window interface
   - Dashboard with task timeline, task cards, settings
   - Voice mode toggle and microphone control
   - Stop button (global shortcut via Tauri)
   - No direct Windows automation capabilities

2. **Backend (Python FastAPI Sidecar)**
   - Authenticated local API (127.0.0.1 only)
   - Task application service with single runner lease
   - Tool executor with typed actions
   - SQLite database manager
   - Ollama Cloud adapter

3. **Task Application Service**
   - Single durable task runner
   - State machine management
   - Event sourcing via immutable task_events
   - Cancellation and recovery handling

4. **Domain Layer**
   - Policy engine for action authorization
   - Context management
   - Skill registry and execution

5. **Tool Executors**
   - System read tools (time, battery, disk, processes, active window)
   - File tools (scoped to approved roots)
   - Application tools (launch/focus/close via registered identity)
   - Package tools (winget operations)
   - GUI interaction tools (UIA primary, OCR fallback)

## Data Model

### SQLite Schema

```sql
-- Tasks table (current state projection)
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    original_request TEXT NOT NULL,
    normalized_goal TEXT,
    state TEXT NOT NULL CHECK(state IN ('created', 'running', 'waiting_for_user', 'completed', 'failed', 'cancelled', 'interrupted')),
    version INTEGER DEFAULT 1,
    active_action_id TEXT,
    selected_skill_version TEXT,
    pending_question TEXT,
    final_result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    terminal_reason TEXT
);

-- Task events (immutable audit log)
CREATE TABLE task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL,
    sequence_num INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Runner lease (single instance enforcement)
CREATE TABLE runner_lease (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    owner_nonce TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Skills registry
CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    state TEXT DEFAULT 'enabled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE skill_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    version TEXT NOT NULL,
    definition TEXT NOT NULL,
    validation_result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);

-- Settings (non-secret only)
CREATE TABLE settings_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Task State Machine

```
created -> running -> waiting_for_user -> running
created -> running -> completed
created -> running -> failed
created -> running -> cancelled
created/running/waiting_for_user -> interrupted (on crash/restart)
interrupted -> running (on explicit resume)
```

## Security Model

1. **Local Boundary**
   - API binds only to 127.0.0.1
   - Per-launch random authentication token
   - Tauri starts single Python sidecar
   - No shell/process execution from frontend

2. **Data Protection**
   - SQLite in user's local app data directory
   - User-only Windows ACLs
   - Secrets in Windows Credential Manager (not SQLite)
   - WAL mode for concurrent reads

3. **Action Policy**
   - All actions require policy approval
   - Model cannot override policy
   - Verification required for all mutating operations
   - Cancellation checks before OS calls

## API Contract

### Authentication
- All requests require `X-Control-Token` header
- Token generated per-launch by Tauri
- Validated on every request

### Endpoints

```
POST /tasks - Create new task
GET /tasks - List tasks
GET /tasks/{id} - Get task details
POST /tasks/{id}/reply - Reply to waiting_for_user task
POST /tasks/{id}/cancel - Cancel task
POST /tasks/{id}/resume - Resume interrupted task

GET /settings - Get settings
PUT /settings - Update settings

POST /voice/start - Start voice session
POST /voice/stop - Stop voice session
POST /voice/audio - Stream audio frames

GET /health - Health check
GET /models - List available models
```

## Voice Processing

1. Dashboard controls microphone permission
2. Audio streamed as PCM frames to sidecar
3. Local VAD detects speech segments
4. Local STT transcribes segments
5. Editable transcript shown in UI
6. "Stop" phrase detected locally
7. Raw audio deleted after transcription (unless recording enabled)

## Tool Execution Rules

1. **System Tools**: Direct OS APIs, no shell parsing
2. **File Tools**: 
   - Scoped to configured roots only
   - No symlinks/junctions/wildcards
   - Recycle Bin for deletions
   - Recheck target before mutation
3. **Application Tools**:
   - Registered application identity only
   - No arbitrary paths/command lines
   - Handle unsaved-work prompts as waiting_for_user
4. **Package Tools**:
   - winget only, fixed argument arrays
   - Exact package ID required
   - No auto-accept of agreements
5. **GUI Tools**:
   - UI Automation first, OCR fallback
   - One interaction per call
   - Re-observe after each action
   - No elevated/secure desktop targets

## Error Handling

1. **Model Decisions**: Max 2 repair attempts, then fail
2. **Cloud Outage**: Honest failure, no silent fallback
3. **Cancellation**: Immediate for observations, between items for batches
4. **Crash Recovery**: Mark action as uncertain, re-observe state
5. **Invalid Input**: Structured error responses with redacted evidence

## Constraints

- Windows 10/11 only
- Standard user privileges (no elevation)
- No browser automation
- No background daemon/tray
- No ambient listening
- Single task execution
- No vector memory systems
- No cross-device control
