# JARVIS Backend Services

This directory contains the core backend services for the JARVIS AI assistant.

## Services Implemented

### 1. Task Runner Service (`task_runner.py`)
Manages task execution with a state machine pattern:
- **Lease Management**: Exclusive runner lease with 30-second heartbeat
- **Task Lifecycle**: Create, transition, cancel tasks with audit logging
- **State Machine**: Enforces valid state transitions (CREATED → PLANNING → EXECUTING → COMPLETED/FAILED/CANCELLED)
- **Idempotency**: Support for idempotency keys to prevent duplicate tasks
- **Event Sourcing**: All state changes logged as events for audit trail

**Usage:**
```python
from services.task_runner import get_runner
from sqlalchemy.orm import Session

db: Session = ...  # Get database session
runner = get_runner(db)

# Acquire lease
if await runner.acquire_lease():
    # Create task
    task = await runner.create_task("Open Chrome and search for Python")
    
    # Transition through states
    await runner.transition_state(
        task_id=task.id,
        new_state=TaskState.PLANNING,
        event_type="task.started_planning",
        event_data={"step": "analyzing_request"}
    )
    
    # Release lease when done
    await runner.release_lease()
```

### 2. Skills System (`skills_system.py`)
Composable skill framework for LLM-invoked actions:
- **Skill Registry**: Central registration and discovery of skills
- **Skill Definitions**: Typed parameters, descriptions, risk levels
- **Execution Engine**: Async execution with validation and error handling
- **Prompt Generation**: Auto-generate skill documentation for LLM context
- **Categories**: SYSTEM, FILE, APPLICATION, PACKAGE, COMMUNICATION, BROWSER, MEDIA, CUSTOM

**Built-in Skills:**
- `system.get_time`: Get current date/time
- `system.get_battery`: Get battery status
- `file.read`: Read file contents

**Usage:**
```python
from services.skills_system import get_registry, initialize_default_skills

# Initialize default skills
initialize_default_skills()

# Get registry
registry = get_registry()

# List all skills
skills = registry.list_skills()

# Search skills
results = registry.search_skills("battery")

# Get skill and execute
skill = registry.get("system.get_time")
result = await skill.execute()
print(result.output)  # ISO format datetime

# Generate prompts for LLM
prompts = registry.get_all_prompts()
```

### 3. Ollama Adapter (`jarvis_backend/services/ollama_adapter.py`)
LLM inference service for local/remote Ollama instances:
- **Chat Completions**: Multi-turn conversation support
- **Streaming**: Async streaming responses
- **Model Management**: List available models
- **Configuration**: Base URL, model selection, timeout, SSL options
- **Generation Endpoint**: Single-turn prompt completion

**Usage:**
```python
from jarvis_backend.services import OllamaAdapter, OllamaConfig, ChatMessage

config = OllamaConfig(
    base_url="http://localhost:11434",
    default_model="llama3"
)
adapter = OllamaAdapter(config)

# Check health
if await adapter.health_check():
    # List models
    models = await adapter.list_models()
    
    # Chat completion
    messages = [
        ChatMessage(role="user", content="What is Python?")
    ]
    response = await adapter.chat(messages)
    print(response.content)
    
    # Streaming chat
    async for chunk in adapter.chat_stream(messages):
        print(chunk, end="", flush=True)
```

### 4. Voice Service (`jarvis_backend/services/voice_service.py`)
Voice processing pipeline (VAD, STT, TTS):
- **VAD (Voice Activity Detection)**: Energy-based speech detection
- **STT (Speech-to-Text)**: Whisper integration for transcription
- **TTS (Text-to-Speech)**: Cross-platform system TTS (Windows SAPI, macOS say, Linux espeak)
- **Streaming Support**: Real-time audio processing

**Usage:**
```python
from jarvis_backend.services import VoiceProcessor, VoiceConfig

config = VoiceConfig(
    sample_rate=16000,
    vad_sensitivity=0.5,
    stt_provider="whisper",
    tts_provider="system"
)
processor = VoiceProcessor(config)

# Speak text
await processor.speak_text("Hello, I am JARVIS")

# Transcribe audio
audio_data = b"..."  # Raw audio bytes
text = await processor.transcribe_audio(audio_data)

# Start listening (requires audio capture integration)
async def on_speech(text):
    print(f"User said: {text}")

await processor.start_listening(on_speech)
```

## Architecture

```
services/
├── __init__.py              # Service exports
├── task_runner.py           # Task state machine
├── skills_system.py         # Skill registry & execution
└── jarvis_backend/
    └── services/
        ├── __init__.py
        ├── ollama_adapter.py    # LLM inference
        └── voice_service.py     # Voice processing
```

## Dependencies

- `sqlalchemy`: Database ORM for task persistence
- `pydantic`: Data validation and settings management
- `httpx`: Async HTTP client for Ollama API
- `psutil`: System information (battery, processes)
- `whisper` (optional): Speech-to-text engine

## Testing

Run service tests:
```bash
cd /workspace/jarvis/backend
python -m pytest services/ -v
```

## Next Steps

1. **Integration Tests**: Add comprehensive tests for each service
2. **Skill Expansion**: Implement remaining skill categories (browser, media, communication)
3. **Voice Pipeline**: Integrate actual audio capture (PyAudio/sounddevice)
4. **Task Executor**: Connect task runner to tool executor for action execution
5. **LLM Orchestrator**: Build agent loop that uses skills based on LLM decisions
