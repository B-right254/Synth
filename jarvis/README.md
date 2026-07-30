# JARVIS - Windows 10/11 Personal Desktop Assistant

[![Tests](https://img.shields.io/badge/tests-74%20passed-green)]()
[![Phase](https://img.shields.io/badge/phase-3%20complete-blue)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F%2F11-lightgrey)]()

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ 
- Windows 10/11 (for full feature support)
- Ollama Cloud API key ([get one free](https://ollama.com))

### 1. Configure Environment

```bash
cd jarvis/backend
cat > .env << EOF
JARVIS_OLLAMA_CLOUD_BASE_URL=https://ollama.com
JARVIS_OLLAMA_API_KEY=your_api_key_here
JARVIS_SELECTED_MODEL=qwen2.5:7b
JARVIS_FILE_ROOTS=C:/Users/YourName/Documents,C:/Users/YourName/Downloads
JARVIS_DATABASE_PATH=C:/Users/YourName/AppData/Local/JARVIS/jarvis.db
EOF
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Backend

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 4. Test It

```bash
# Health check
curl http://127.0.0.1:8000/api/health

# Create a task
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"original_request": "What time is it?"}'
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [CONFIGURATION.md](CONFIGURATION.md) | Detailed environment setup guide |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Real-world testing scenarios & checklist |
| [PHASE3_REPORT.md](PHASE3_REPORT.md) | Phase 3 implementation details |
| [FINAL_STATUS.md](FINAL_STATUS.md) | Project status overview |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture deep-dive |
| [docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) | Complete acceptance test map |

---

## ✅ Current Status: Phase 3 Complete

### Implemented Features

#### Core Task System
- ✅ Immutable event ledger for task state
- ✅ LLM-driven decision loop (observe → act → verify)
- ✅ Typed tool system with policy evaluation
- ✅ User interaction (questions & replies)

#### Crash Recovery (NEW in Phase 3)
- ✅ Stale lease detection (30-second heartbeat timeout)
- ✅ Automatic task interruption on crash
- ✅ Resume endpoint for manual recovery
- ✅ Re-observation before continuing mutations

#### Voice Pipeline (NEW in Phase 3)
- ✅ PyAudio/WebRTC VAD for voice activity detection
- ✅ whisper.cpp STT (Windows) / openai-whisper (Linux/Mac)
- ✅ Windows SAPI5 TTS integration
- ✅ Session-based audio streaming API

#### GUI Automation
- ✅ Screen observation with OCR
- ✅ Window focus management
- ✅ Element invocation
- ✅ Keyboard input (type, hotkeys, click)

### Test Coverage

**74 tests passing** across:
- Unit tests (tools, services, adapters)
- Integration tests (task execution loop)
- Voice pipeline tests
- GUI tools tests

Run tests:
```bash
cd jarvis/backend
python -m pytest tests/ -v
```

---

## 🏗️ Architecture

```
jarvis/
├── backend/              # FastAPI sidecar
│   ├── api/             # REST endpoints
│   ├── adapters/        # Ollama Cloud, external services
│   ├── core/            # Config, auth, database
│   ├── domain/          # State machine logic
│   ├── services/        # Business logic (tasks, voice, skills)
│   ├── tools/           # Tool implementations
│   └── models/          # SQLAlchemy ORM models
├── frontend/            # React + TypeScript UI (optional)
├── tasks/               # Skill definitions
└── docs/                # Documentation
```

### Key Design Decisions

1. **Single-task execution** - Lease-based serialization prevents conflicts
2. **Immutable audit trail** - Every action logged as append-only event
3. **Observation-first** - LLM must observe before mutating state
4. **Security boundaries** - File roots, no browser automation, standard user privileges
5. **Windows-first** - Optimized for Windows 10/11, graceful degradation elsewhere

---

## 🔧 Available Tools

### System Tools
- `get_time`, `get_battery_status`, `get_disk_usage`
- `list_processes`, `get_active_window`

### File Tools
- `list_directory`, `read_file`, `create_file`
- `write_file`, `move_file`, `copy_file`, `delete_file`

### Application Tools
- `list_apps`, `launch_app`, `focus_app`, `close_app`

### Package Management
- `search_packages`, `list_packages`
- `install_package`, `uninstall_package`

### GUI Interaction
- `observe_gui`, `focus_window`, `invoke_element`
- `click`, `type_text`, `send_hotkey`, `set_value`

### Voice (Optional)
- `start_voice_session`, `process_audio`, `speak_response`

---

## 🎯 Example Use Cases

### 1. Simple Query
```json
POST /api/tasks
{
  "original_request": "What's my battery level?"
}
```

### 2. File Operation
```json
POST /api/tasks
{
  "original_request": "Create a file called notes.txt with today's date"
}
```

### 3. Application Control
```json
POST /api/tasks
{
  "original_request": "Open Notepad and type 'Hello World'"
}
```

### 4. Multi-step Task
```json
POST /api/tasks
{
  "original_request": "Find all PDF files in Documents and list them"
}
```

---

## ⚠️ Limitations

1. **Platform**: Windows 10/11 recommended (Linux/Mac have limited GUI support)
2. **No Browser Automation**: Intentional security constraint
3. **Standard Privileges Only**: No admin/elevated operations
4. **Single Concurrent Task**: Serialized execution via lease mechanism
5. **LLM Dependency**: Requires Ollama Cloud API key (free tier available)

---

## 🛣️ Roadmap

### Phase 4 (Next)
- [ ] Frontend dashboard integration
- [ ] Skill library expansion
- [ ] Performance optimization
- [ ] Enhanced error handling
- [ ] User feedback incorporation

### Future Considerations
- Local LLM support (Ollama local instances)
- Extended tool ecosystem
- Multi-user support
- Cloud sync capabilities

---

## 🤝 Contributing

This is a proprietary project. For questions or issues, contact the development team.

---

## 📄 License

Proprietary - All rights reserved

---

**Last Updated**: July 2025  
**Version**: 0.1.0 (Phase 3 Complete)
