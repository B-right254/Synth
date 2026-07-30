# JARVIS Configuration Guide

## Environment Setup

JARVIS requires environment variables to be set for production use. Create a `.env` file in the `jarvis/backend/` directory or set system environment variables with the `JARVIS_` prefix.

## Required Configuration

### Ollama Cloud (LLM Provider)

JARVIS uses Ollama Cloud for LLM inference. You must configure:

```bash
# Ollama Cloud API credentials
JARVIS_OLLAMA_CLOUD_BASE_URL=https://ollama.com
JARVIS_OLLAMA_API_KEY=your_api_key_here
JARVIS_SELECTED_MODEL=qwen2.5:7b  # Or another supported model
```

**Getting Your API Key:**
1. Visit [Ollama Cloud](https://ollama.com)
2. Create an account or sign in
3. Navigate to API settings
4. Generate a new API key
5. Copy the key to your environment

**Available Models:**
- `qwen2.5:7b` - Balanced performance (recommended)
- `qwen2.5:14b` - Higher accuracy, slower
- `llama3.1:8b` - Alternative option

To list available models after setup:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" https://ollama.com/api/tags
```

### Database Path

```bash
# SQLite database location (Windows example)
JARVIS_DATABASE_PATH=C:\Users\YourName\AppData\Local\JARVIS\jarvis.db
```

### File Roots (Security)

Define approved directories for file operations:

```bash
# Comma-separated list of allowed directories
JARVIS_FILE_ROOTS=C:\Users\YourName\Documents,C:\Users\YourName\Downloads
```

### Voice Configuration (Optional)

```bash
# Enable/disable voice features
JARVIS_VOICE_ENABLED=true

# STT model path (whisper.cpp model)
JARVIS_STT_MODEL_PATH=C:\models\ggml-base.bin

# TTS voice name (Windows SAPI5)
JARVIS_TTS_VOICE_NAME=Microsoft Zira Desktop
```

### Security Token

The control token is generated per-launch by the Tauri desktop app. For direct API testing:

```bash
JARVIS_CONTROL_TOKEN=$(python -c "import uuid; print(str(uuid.uuid4()))")
```

## Quick Test

After configuration, test connectivity:

```bash
cd jarvis/backend
python -c "from backend.core.config import settings; print('Config OK:', bool(settings.ollama_api_key))"
```

## Production Checklist

- [ ] Ollama API key configured
- [ ] Model selected and verified
- [ ] Database path writable
- [ ] File roots defined (security requirement)
- [ ] Voice models downloaded (if using voice)
- [ ] Control token generated (for API access)

## Troubleshooting

**"Invalid API key" error:**
- Verify key is copied correctly (no extra spaces)
- Check Ollama Cloud account status
- Ensure network connectivity

**"No models available":**
- Pull a model: `ollama pull qwen2.5:7b` (if using local Ollama)
- Verify API endpoint URL

**Database errors:**
- Ensure directory exists and is writable
- Check file permissions on Windows
