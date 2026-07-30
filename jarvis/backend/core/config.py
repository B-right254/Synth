"""
Core configuration and constants for JARVIS backend.
"""

from pydantic_settings import BaseSettings
from typing import List
import uuid


class Settings(BaseSettings):
    """Application settings."""
    
    # Server configuration
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Security
    control_token: str = ""  # Set per-launch by Tauri
    
    # Database
    database_path: str = ""  # Set to user's local app data on Windows
    
    # Ollama Cloud
    ollama_cloud_base_url: str = "https://ollama.com"
    ollama_api_key: str = ""  # From Windows Credential Manager
    selected_model: str = ""  # Selected from model list
    
    # File roots (approved directories for file operations)
    file_roots: List[str] = []
    
    # Task limits
    max_actions_per_task: int = 100
    max_cloud_requests_per_task: int = 50
    max_input_tokens: int = 50000
    max_output_tokens: int = 4000
    max_elapsed_time_seconds: int = 3600
    max_repair_attempts: int = 2
    
    # Voice
    voice_enabled: bool = True
    stt_model_path: str = ""  # Path to pinned STT model
    tts_voice_name: str = ""  # Name of pinned TTS voice
    
    class Config:
        env_prefix = "JARVIS_"
        env_file = ".env"


settings = Settings()


def generate_control_token() -> str:
    """Generate a random per-launch control token."""
    return str(uuid.uuid4())
