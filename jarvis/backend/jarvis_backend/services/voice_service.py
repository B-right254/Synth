"""
Voice Processing Service
Handles Voice Activity Detection (VAD), Speech-to-Text (STT), and Text-to-Speech (TTS).
Provides cross-platform audio capture and playback.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

class VADState:
    """Voice Activity Detection states."""
    SILENT = "silent"
    SPEAKING = "speaking"
    
class VoiceConfig:
    """Configuration for voice processing."""
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        vad_sensitivity: float = 0.5,
        silence_duration_ms: int = 1000,
        stt_provider: str = "whisper",
        tts_provider: str = "system",
        audio_input_device: Optional[str] = None,
        audio_output_device: Optional[str] = None
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.vad_sensitivity = vad_sensitivity
        self.silence_duration_ms = silence_duration_ms
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self.audio_input_device = audio_input_device
        self.audio_output_device = audio_output_device

class BaseVAD(ABC):
    """Abstract base class for Voice Activity Detection."""
    
    @abstractmethod
    async def process_audio(self, audio_data: bytes) -> VADState:
        """Process audio chunk and return VAD state."""
        pass
        
    @abstractmethod
    async def reset(self):
        """Reset VAD state."""
        pass

class BaseSTT(ABC):
    """Abstract base class for Speech-to-Text."""
    
    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio to text."""
        pass
        
    @abstractmethod
    async def transcribe_stream(self, audio_generator: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """Stream transcription of audio chunks."""
        pass

class BaseTTS(ABC):
    """Abstract base class for Text-to-Speech."""
    
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech from text, return audio data."""
        pass
        
    @abstractmethod
    async def synthesize_to_file(self, text: str, output_path: Path) -> Path:
        """Synthesize speech and save to file."""
        pass

class SimpleVAD(BaseVAD):
    """
    Simple energy-based VAD implementation.
    In production, replace with WebRTC VAD or Silero VAD.
    """
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.state = VADState.SILENT
        self.silence_counter = 0
        self.threshold = 1000 * (1.0 - config.vad_sensitivity)  # Simple energy threshold
        
    async def process_audio(self, audio_data: bytes) -> VADState:
        """Calculate RMS energy to detect speech."""
        if len(audio_data) < 2:
            return self.state
            
        # Calculate RMS energy (simplified)
        total = 0
        samples = len(audio_data) // 2
        for i in range(samples):
            sample = int.from_bytes(audio_data[i*2:(i+1)*2], byteorder='little', signed=True)
            total += sample * sample
            
        rms = (total / samples) ** 0.5 if samples > 0 else 0
        
        if rms > self.threshold:
            self.state = VADState.SPEAKING
            self.silence_counter = 0
        else:
            self.silence_counter += 1
            # Transition to silent after sustained silence
            if self.silence_counter > (self.config.silence_duration_ms / 100):
                self.state = VADState.SILENT
                
        return self.state
        
    async def reset(self):
        """Reset VAD state."""
        self.state = VADState.SILENT
        self.silence_counter = 0

class WhisperSTT(BaseSTT):
    """
    Whisper-based Speech-to-Text implementation.
    Uses whisper.cpp or transformers library.
    """
    
    def __init__(self, config: VoiceConfig, model_path: Optional[str] = None):
        self.config = config
        self.model_path = model_path
        self._model = None
        
    async def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            try:
                # Attempt to import whisper (would need to be installed)
                import whisper
                self._model = whisper.load_model(self.model_path or "base")
                logger.info("Whisper model loaded successfully")
            except ImportError:
                logger.warning("Whisper not installed, using stub implementation")
                self._model = "stub"
                
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio to text."""
        await self._load_model()
        
        if self._model == "stub":
            # Stub implementation for when whisper is not available
            logger.debug("Using STT stub - no transcription performed")
            return ""
            
        try:
            # Save audio to temp file for whisper processing
            import tempfile
            import numpy as np
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                # Write WAV header and audio data (simplified)
                # In production, use proper WAV encoding
                f.write(audio_data)
                temp_path = f.name
                
            result = self._model.transcribe(temp_path)
            Path(temp_path).unlink(missing_ok=True)
            return result.get("text", "")
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
            
    async def transcribe_stream(self, audio_generator: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """Stream transcription - accumulates audio and transcribes periodically."""
        await self._load_model()
        
        if self._model == "stub":
            async for _ in audio_generator:
                yield ""
            return
            
        buffer = b""
        chunk_count = 0
        
        async for chunk in audio_generator:
            buffer += chunk
            chunk_count += 1
            
            # Transcribe every 5 chunks (adjust based on chunk size)
            if chunk_count >= 5 and len(buffer) > 0:
                result = await self.transcribe(buffer)
                if result:
                    yield result
                buffer = b""
                chunk_count = 0
                
        # Final transcription of remaining buffer
        if buffer:
            result = await self.transcribe(buffer)
            if result:
                yield result

class SystemTTS(BaseTTS):
    """
    System-native Text-to-Speech implementation.
    Uses platform-specific TTS engines.
    """
    
    def __init__(self, config: VoiceConfig, voice: Optional[str] = None):
        self.config = config
        self.voice = voice
        
    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech - returns empty bytes as this is fire-and-play."""
        # For system TTS, we typically play directly rather than returning audio
        # This method would require a TTS engine that returns audio (like Piper, Coqui, etc.)
        logger.debug(f"TTS requested for {len(text)} chars (stub implementation)")
        return b""
        
    async def synthesize_to_file(self, text: str, output_path: Path) -> Path:
        """Synthesize speech and save to file using system TTS."""
        import platform
        import subprocess
        
        system = platform.system()
        
        try:
            if system == "Windows":
                # Use PowerShell SAPI
                script = f'''
                Add-Type -AssemblyName System.Speech
                $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $speak.Speak("{text.replace('"', '`"')}")
                '''
                # Note: Direct file output requires more complex setup
                logger.info(f"Windows TTS would speak: {text[:50]}...")
                
            elif system == "Darwin":  # macOS
                # Use say command
                cmd = ["say", "-o", str(output_path), text]
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info(f"macOS TTS saved to {output_path}")
                
            else:  # Linux
                # Try espeak or festival
                cmd = ["espeak", "-w", str(output_path), text]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    logger.info(f"Linux TTS (espeak) saved to {output_path}")
                except FileNotFoundError:
                    logger.warning("espeak not found, TTS unavailable")
                    
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            
        return output_path
        
    async def speak(self, text: str) -> bool:
        """Speak text directly using system TTS."""
        import platform
        import subprocess
        
        system = platform.system()
        
        try:
            if system == "Windows":
                # Use PowerShell
                script = f'''
                Add-Type -AssemblyName System.Speech
                $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $speak.Speak("{text.replace('"', '`"')}")
                '''
                subprocess.run(["powershell", "-Command", script], capture_output=True)
                
            elif system == "Darwin":
                subprocess.run(["say", text], check=True, capture_output=True)
                
            else:  # Linux
                cmd = ["espeak", text]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                except FileNotFoundError:
                    logger.warning("espeak not found")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Speech playback failed: {e}")
            return False

class VoiceProcessor:
    """
    Main voice processing orchestrator.
    Coordinates VAD, STT, and TTS components.
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.vad = SimpleVAD(self.config)
        self.stt = WhisperSTT(self.config)
        self.tts = SystemTTS(self.config)
        self._is_listening = False
        self._speech_callback: Optional[Callable[[str], None]] = None
        
    async def start_listening(self, callback: Callable[[str], None]):
        """Start listening for speech and call callback with transcribed text."""
        self._is_listening = True
        self._speech_callback = callback
        logger.info("Voice processor started listening")
        # In production, this would start an audio capture loop
        
    async def stop_listening(self):
        """Stop listening."""
        self._is_listening = False
        await self.vad.reset()
        logger.info("Voice processor stopped listening")
        
    async def process_voice_input(self, audio_data: bytes) -> Optional[str]:
        """Process incoming audio and return transcription if speech detected."""
        if not self._is_listening:
            return None
            
        state = await self.vad.process_audio(audio_data)
        
        if state == VADState.SPEAKING:
            # Buffer audio for transcription
            # In production, implement proper buffering and endpoint detection
            pass
        elif state == VADState.SILENT:
            # If transitioning from speaking to silent, transcribe buffered audio
            # This is simplified; real implementation needs proper buffering
            pass
            
        return None
        
    async def speak_text(self, text: str) -> bool:
        """Convert text to speech and play it."""
        return await self.tts.speak(text)
        
    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio data to text."""
        return await self.stt.transcribe(audio_data)

# Factory function
def get_voice_processor(config: Optional[VoiceConfig] = None) -> VoiceProcessor:
    """Create a voice processor instance."""
    return VoiceProcessor(config)
