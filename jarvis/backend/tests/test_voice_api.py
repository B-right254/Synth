"""
Test Voice API Endpoints
Tests for the voice processing API endpoints.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from backend.main import app, db_manager
from backend.models.database import Base, get_db, set_db_manager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import base64


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_voice.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    from backend.api.routes import router
    from fastapi import Depends
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestVoiceEndpoints:
    """Test voice API endpoints."""
    
    def test_start_voice_session(self, client):
        """Test starting a voice session."""
        response = client.post("/api/v1/voice/start")
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "listening"
        assert len(data["session_id"]) > 0
    
    def test_end_voice_session(self, client):
        """Test ending a voice session."""
        # Start a session first
        start_response = client.post("/api/v1/voice/start")
        session_id = start_response.json()["session_id"]
        
        # End the session
        response = client.post(f"/api/v1/voice/{session_id}/end")
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "ended"
    
    def test_process_voice_audio(self, client):
        """Test processing audio frames."""
        # Start a session first
        start_response = client.post("/api/v1/voice/start")
        session_id = start_response.json()["session_id"]
        
        # Create dummy audio data (silence - all zeros)
        # 160 samples of 16-bit audio = 320 bytes
        audio_data = b'\x00' * 320
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        response = client.post(
            f"/api/v1/voice/{session_id}/audio",
            json={
                "session_id": session_id,
                "audio_data": audio_base64,
                "sample_rate": 16000,
                "channels": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "vad_state" in data
        assert "transcription" in data
        assert "is_speaking" in data
    
    def test_process_voice_audio_invalid_base64(self, client):
        """Test processing audio with invalid base64 data."""
        # Start a session first
        start_response = client.post("/api/v1/voice/start")
        session_id = start_response.json()["session_id"]
        
        response = client.post(
            f"/api/v1/voice/{session_id}/audio",
            json={
                "session_id": session_id,
                "audio_data": "invalid_base64!!!",
                "sample_rate": 16000,
                "channels": 1
            }
        )
        
        assert response.status_code == 400
        assert "Invalid audio data" in response.json()["detail"]
    
    def test_speak_text(self, client):
        """Test text-to-speech endpoint."""
        response = client.post(
            "/api/v1/voice/speak",
            json={"text": "Hello, this is a test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "text" in data
    
    def test_speak_text_empty(self, client):
        """Test text-to-speech with empty text."""
        response = client.post(
            "/api/v1/voice/speak",
            json={"text": ""}
        )
        
        assert response.status_code == 400
        assert "Text is required" in response.json()["detail"]
    
    def test_speak_text_missing(self, client):
        """Test text-to-speech with missing text field."""
        response = client.post(
            "/api/v1/voice/speak",
            json={}
        )
        
        assert response.status_code == 400  # Returns 400 from manual validation


class TestVoiceWorkflow:
    """Test complete voice workflows."""
    
    def test_complete_voice_session_workflow(self, client):
        """Test a complete voice session workflow."""
        # 1. Start session
        start_response = client.post("/api/v1/voice/start")
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]
        
        # 2. Send some audio frames (silence)
        audio_data = b'\x00' * 320
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        for i in range(3):
            audio_response = client.post(
                f"/api/v1/voice/{session_id}/audio",
                json={
                    "session_id": session_id,
                    "audio_data": audio_base64,
                    "sample_rate": 16000,
                    "channels": 1
                }
            )
            assert audio_response.status_code == 200
        
        # 3. Speak some text
        speak_response = client.post(
            "/api/v1/voice/speak",
            json={"text": "Task completed"}
        )
        assert speak_response.status_code == 200
        
        # 4. End session
        end_response = client.post(f"/api/v1/voice/{session_id}/end")
        assert end_response.status_code == 200
        assert end_response.json()["status"] == "ended"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
