# JARVIS Acceptance Test Map

## Phase -1: Foundation & Tooling

### F-1.1 Project Skeleton
- [ ] Directory structure created (backend, frontend, tasks, docs, config, tests)
- [ ] Python virtual environment setup
- [ ] Node.js environment setup
- [ ] Git repository initialized with proper .gitignore
- [ ] Basic CI/CD pipeline configured

### F-1.2 Backend Core
- [ ] FastAPI application initialized
- [ ] Authentication middleware implemented (X-Control-Token)
- [ ] SQLite database connection with WAL mode
- [ ] Database schema migrations implemented
- [ ] Health check endpoint functional

### F-1.3 Frontend Core
- [ ] React application initialized with Vite
- [ ] Tauri configuration completed
- [ ] Basic dashboard layout implemented
- [ ] Authentication token handshake with Tauri
- [ ] API client with authentication

### F-1.4 Task Ledger
- [ ] Tasks CRUD operations functional
- [ ] Task events immutable append-only writes
- [ ] Runner lease acquisition and validation
- [ ] State machine transitions enforced
- [ ] Optimistic locking with version numbers

### F-1.5 Tool Executor Framework
- [ ] Pydantic schemas for all tool inputs/outputs
- [ ] Tool registry with discovery
- [ ] Execution result structure (success, data, error, evidence, duration_ms)
- [ ] Policy evaluation framework
- [ ] Verification framework

## Phase 0: Core Loop & Cloud Integration

### C-0.1 Ollama Cloud Adapter
- [ ] Provider authentication health check
- [ ] Model list retrieval and selection
- [ ] Native tool call formatting
- [ ] Response parsing with schema validation
- [ ] Rate limit and error handling
- [ ] Token budget tracking

### C-0.2 Model Decision Engine
- [ ] Context builder with redaction
- [ ] Tool schema exposure to model
- [ ] Single decision enforcement
- [ ] Parallel call rejection
- [ ] Repair attempt limiting (max 2)
- [ ] Decision validation before execution

### C-0.3 Task Runner
- [ ] Single task execution lease
- [ ] Policy evaluation before actions
- [ ] Action commit before execution
- [ ] Verification after execution
- [ ] State transition on completion
- [ ] Cancellation check points

### C-0.4 System Read Tools
- [ ] Time/date tool with direct OS API
- [ ] Battery status tool
- [ ] Disk space tool
- [ ] Process list tool (redacted)
- [ ] Active window tool
- [ ] All tools return structured evidence

### C-0.5 Basic File Tools
- [ ] Configured root directories
- [ ] List directory (no symlinks/junctions)
- [ ] Read file (bounded size)
- [ ] Create file with verification
- [ ] Write file with verification
- [ ] Move/copy with target recheck
- [ ] Delete to Recycle Bin

## Phase 1: Applications & GUI

### A-1.1 Application Tools
- [ ] List installed applications (registered identity)
- [ ] Launch application by registered ID
- [ ] Focus application window
- [ ] Close application gracefully
- [ ] Handle unsaved-work prompts as waiting_for_user
- [ ] No arbitrary executable paths

### A-1.2 Package Management
- [ ] winget search with exact ID results
- [ ] winget list installed packages
- [ ] winget install with exact package ID
- [ ] winget uninstall with confirmation
- [ ] Fixed argument arrays only
- [ ] No auto-accept of agreements

### A-1.3 GUI Observation
- [ ] UI Automation COM MTA worker thread
- [ ] Active window identification
- [ ] Bounded UIA element query
- [ ] OCR fallback for non-UIA elements
- [ ] Screenshot reference generation
- [ ] Fresh timestamp on all observations

### A-1.4 GUI Interaction
- [ ] Focus target window
- [ ] UIA pattern invoke
- [ ] UIA value set
- [ ] Coordinate click (physical pixels, DPI normalized)
- [ ] Keyboard input
- [ ] Hotkey execution
- [ ] Scroll interaction
- [ ] Re-observation after each action
- [ ] One interaction per call limit

### A-1.5 GUI Safety
- [ ] Elevated process detection and rejection
- [ ] UAC dialog detection
- [ ] Secure desktop detection
- [ ] Stale target detection
- [ ] Missing target handling
- [ ] Medium-integrity only enforcement

## Phase 2: Voice & Polish

### V-2.1 Voice Capture
- [ ] Microphone permission via dashboard
- [ ] PCM frame streaming to sidecar
- [ ] Voice session start/stop lifecycle
- [ ] Automatic stop on minimize/close/lock
- [ ] Permission loss handling

### V-2.2 Speech Processing
- [ ] Local VAD implementation
- [ ] Local STT model integration
- [ ] Segment completion detection
- [ ] Editable transcript display
- [ ] Stop phrase detection
- [ ] Raw audio cleanup after transcription

### V-2.3 Text-to-Speech
- [ ] Local TTS engine integration
- [ ] Evidence-based result narration
- [ ] Concise summary generation
- [ ] Voice selection in settings

### V-2.4 Dashboard Polish
- [ ] Task timeline visualization
- [ ] Task card with state indicators
- [ ] Settings panel
- [ ] Voice mode toggle
- [ ] Stop button (always visible)
- [ ] Cancellation feedback

## Phase 3: Skills & Recovery

### S-3.1 Skill System
- [ ] Declarative skill definition format
- [ ] Skill registration and validation
- [ ] Skill versioning
- [ ] Skill enable/disable
- [ ] run_skill tool implementation
- [ ] Skill proposal and review workflow

### S-3.2 Crash Recovery
- [ ] Lease heartbeat mechanism
- [ ] Stale lease detection
- [ ] Interrupted task identification
- [ ] Uncertain action marking
- [ ] State re-observation on resume
- [ ] No blind action rerun

### S-3.3 Cancellation Refinement
- [ ] Immediate cancellation for observations
- [ ] Between-item cancellation for batches
- [ ] Before-replace cancellation for atomic writes
- [ ] Partial result reporting
- [ ] cancellation_pending state handling
- [ ] Package uninstall inspection

## Security & Compliance Tests

### SEC-1 Local Boundary
- [ ] API binds only to 127.0.0.1
- [ ] Authentication token required on all requests
- [ ] Token validated on every request
- [ ] No shell execution from frontend
- [ ] Single sidecar launch only
- [ ] Tauri capabilities restricted

### SEC-2 Data Protection
- [ ] SQLite in user's local app data
- [ ] User-only ACLs on data directory
- [ ] No secrets in SQLite
- [ ] Secrets in Credential Manager mock
- [ ] WAL mode enabled
- [ ] Transaction isolation verified

### SEC-3 Action Policy
- [ ] Policy evaluated before all actions
- [ ] Model cannot override policy
- [ ] Ambiguous targets require clarification
- [ ] Direct instructions skip confirmation
- [ ] External commitments flagged

### SEC-4 Verification
- [ ] All mutating actions have verifiers
- [ ] Fresh state read after mutation
- [ ] Evidence captured in task_events
- [ ] Redacted evidence in model context
- [ ] Full evidence in audit log

## Error Handling Tests

### ERR-1 Model Errors
- [ ] Invalid decision detected
- [ ] Repair request sent (attempt 1)
- [ ] Repair request sent (attempt 2)
- [ ] Fail after max attempts
- [ ] MODEL_DECISION_INVALID code returned

### ERR-2 Cloud Errors
- [ ] Authentication failure handled
- [ ] Rate limit respected
- [ ] Model unavailable handled
- [ ] Malformed response handled
- [ ] No silent fallback to local model

### ERR-3 Cancellation Errors
- [ ] Cancel during observation
- [ ] Cancel during GUI interaction
- [ ] Cancel during file batch
- [ ] Cancel during package operation
- [ ] Partial results reported

### ERR-4 Recovery Errors
- [ ] Simulated crash during action
- [ ] Lease expiry detected
- [ ] Interrupted task identified
- [ ] Resume re-observes state
- [ ] No duplicate action execution

## Platform Constraints

### WIN-1 Windows Specific
- [ ] Windows 10/11 API usage verified
- [ ] Standard user privileges only
- [ ] No elevation attempts
- [ ] UIAccess not used
- [ ] Medium integrity maintained

### WIN-2 Exclusions Verified
- [ ] No browser automation
- [ ] No PowerShell/CMD execution
- [ ] No registry access
- [ ] No service installation
- [ ] No background daemon
- [ ] No ambient listening
- [ ] No clipboard capture
- [ ] No filesystem watchers

## Performance Benchmarks

### PERF-1 Responsiveness
- [ ] API response time < 100ms (non-model)
- [ ] Dashboard render < 50ms
- [ ] Voice segment latency < 500ms
- [ ] Task state update propagation < 200ms

### PERF-2 Resource Usage
- [ ] Memory footprint < 500MB
- [ ] CPU idle < 5%
- [ ] Database size growth bounded
- [ ] No memory leaks over 8-hour session

### PERF-3 Scalability
- [ ] 1000+ task events handled
- [ ] 100+ skills registered
- [ ] Concurrent dashboard + voice session
- [ ] Stable over 24-hour uptime
