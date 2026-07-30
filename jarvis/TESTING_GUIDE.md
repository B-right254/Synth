# JARVIS Real-World Testing Guide

## ✅ System Readiness Status

**All 74 tests passing** - Core functionality verified:
- Task management & crash recovery
- Voice pipeline (VAD, STT, TTS)
- Tool execution system
- GUI automation tools
- Integration workflows

## ⚠️ Required Configuration Before Testing

### 1. LLM Connection (CRITICAL)

JARVIS requires **Ollama Cloud API credentials** to make decisions:

```bash
# Create .env file in jarvis/backend/
cd jarvis/backend
cat > .env << EOF
JARVIS_OLLAMA_CLOUD_BASE_URL=https://ollama.com
JARVIS_OLLAMA_API_KEY=your_api_key_here
JARVIS_SELECTED_MODEL=qwen2.5:7b
EOF
```

**Get your API key:**
1. Visit https://ollama.com
2. Sign up / Log in
3. Go to API settings
4. Generate API key
5. Copy to `.env` file

**Verify connection:**
```bash
cd jarvis/backend
python -c "from backend.adapters.ollama_adapter import get_adapter; import asyncio; adapter = get_adapter(); print('Connected:', asyncio.run(adapter.check_health()))"
```

### 2. File Security Roots (REQUIRED)

Define approved directories for file operations:

```bash
# Add to .env file
JARVIS_FILE_ROOTS=/home/user/Documents,/home/user/Downloads
```

On Windows:
```
JARVIS_FILE_ROOTS=C:\Users\YourName\Documents,C:\Users\YourName\Downloads
```

### 3. Database Path

```bash
# Add to .env file
JARVIS_DATABASE_PATH=/home/user/.local/share/jarvis/jarvis.db
```

On Windows:
```
JARVIS_DATABASE_PATH=C:\Users\YourName\AppData\Local\JARVIS\jarvis.db
```

## 🚀 Starting the Backend

```bash
cd jarvis/backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## 🧪 Testing Scenarios

### Test 1: Health Check
```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database_connected": true,
  "cloud_configured": true
}
```

### Test 2: Create a Simple Task
```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_CONTROL_TOKEN" \
  -d '{
    "original_request": "What time is it?",
    "normalized_goal": "Tell the user the current time"
  }'
```

### Test 3: Voice Session (Optional)
```bash
# Start voice session
curl -X POST http://127.0.0.1:8000/api/voice/start

# Returns session_id for audio streaming
```

## 📋 Acceptance Test Checklist

#### Phase 1: Core Task Flow
- [ ] Task creation starts execution loop
- [ ] LLM makes observe → act → verify decisions
- [ ] Task completes with success/failure
- [ ] Events are logged immutably

#### Phase 2: User Interaction
- [ ] LLM requests clarification when needed
- [ ] User can reply to pending questions
- [ ] Task resumes after user input
- [ ] Conversation history is preserved

#### Phase 3: Crash Recovery (NEW)
- [ ] Stale lease detection marks task as `interrupted`
- [ ] Resume endpoint restores interrupted tasks
- [ ] Re-observation occurs before continuing mutations
- [ ] Audit trail shows interruption and recovery

#### Voice Pipeline (NEW)
- [ ] VAD detects speech vs silence
- [ ] STT transcribes audio to text
- [ ] TTS converts responses to speech
- [ ] Voice session manages state correctly

## 🔍 Debugging Tips

### LLM Connection Issues
```bash
# Test Ollama connectivity
curl -H "Authorization: Bearer YOUR_KEY" https://ollama.com/api/tags

# Check logs for errors
tail -f uvicorn.log | grep -i ollama
```

### Task Stuck in Running State
```bash
# Check lease status
curl http://127.0.0.1:8000/api/tasks/{task_id}

# Force release (if crashed)
# Restart backend - stale lease will be detected automatically
```

### Voice Not Working
```bash
# Verify dependencies
python -c "import webrtcvad, whispercpp, pyttsx3; print('Voice deps OK')"

# Check audio devices (Windows)
# Ensure microphone permissions are granted
```

## 📊 Expected Performance

- **Task startup**: < 2 seconds
- **LLM decision**: 1-5 seconds (depending on model)
- **Tool execution**: < 1 second (most tools)
- **Voice processing**: Real-time (< 500ms latency)

## ⛔ Known Limitations

1. **Platform**: Windows 10/11 only (some features degrade gracefully on Linux/Mac)
2. **Browser Automation**: Intentionally not supported (security constraint)
3. **Elevated Privileges**: Not required, but limits some system operations
4. **Concurrent Tasks**: Single task execution (lease-based serialization)

## 📝 Next Steps After Testing

1. Document any bugs or unexpected behavior
2. Record performance metrics
3. Test edge cases (network failures, large files, etc.)
4. Validate security constraints (file roots, no browser automation)
5. Prepare Phase 4 roadmap based on findings

---

**Support**: Check `/workspace/jarvis/docs/` for architecture details and API documentation.
