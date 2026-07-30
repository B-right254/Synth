# JARVIS

Windows 10/11 Personal Desktop Assistant

## Project Structure

```
jarvis/
├── backend/           # Python FastAPI sidecar
│   ├── api/          # API routes and schemas
│   ├── core/         # Core configuration, auth, database
│   ├── domain/       # Domain logic and state machine
│   ├── services/     # Business services
│   ├── tools/        # Tool executors and implementations
│   ├── adapters/     # External service adapters (Ollama Cloud)
│   └── models/       # Database models
├── frontend/         # React + TypeScript UI
│   └── src/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       ├── store/
│       └── types/
├── tasks/            # Task definitions and skills
├── docs/             # Documentation
├── config/           # Configuration files
└── tests/            # Test suite
```

## Quick Start

### Backend

```bash
cd jarvis/backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

### Frontend

```bash
cd jarvis/frontend
npm install
npm run dev
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Acceptance Tests

See [docs/ACCEPTANCE_TESTS.md](docs/ACCEPTANCE_TESTS.md) for the complete test map.

## Key Features

- **Local Dashboard**: React-based UI with task timeline and voice controls
- **Authenticated API**: Per-launch control token for security
- **Durable Tasks**: SQLite-backed task ledger with immutable events
- **Tool System**: Typed tools with policy evaluation and verification
- **Ollama Cloud Integration**: Native tool calls for LLM decisions
- **Voice Support**: Local VAD, STT, and TTS (Windows-only)
- **Windows Automation**: UI Automation and OCR for GUI interaction

## Platform

- **Target**: Windows 10/11 only
- **Privileges**: Standard user (no elevation)
- **Constraints**: No browser automation, no background daemon

## License

Proprietary - All rights reserved
