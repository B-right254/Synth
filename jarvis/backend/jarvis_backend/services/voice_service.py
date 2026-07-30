"""
Voice Processing Service
Handles Voice Activity Detection (VAD), Speech-to-Text (STT), and Text-to-Speech (TTS).
Provides cross-platform audio capture and playback.
"""
import asyncio
import logging
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator, Callable, List
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

class PyAudioVAD(BaseVAD):
    """
    WebRTC VAD implementation using PyAudio.
    Provides robust voice activity detection with configurable sensitivity.
    """
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.state = VADState.SILENT
        self.silence_counter = 0
        self._vad = None
        self._audio_buffer = []
        self._sample_rate = config.sample_rate
        self._frame_duration_ms = 30  # WebRTC VAD works with 10/20/30ms frames
        self._load_vad()
        
    def _load_vad(self):
        """Load WebRTC VAD model."""
        try:
            import webrtcvad
            # Mode 0-3: higher is more aggressive (we use 2 as default)
            mode = int(self.config.vad_sensitivity * 3)
            self._vad = webrtcvad.Vad(mode)
            logger.info(f"WebRTC VAD loaded with mode {mode}")
        except ImportError:
            logger.warning("WebRTC VAD not available, falling back to SimpleVAD")
            self._vad = None
            
    async def process_audio(self, audio_data: bytes) -> VADState:
        """Process audio chunk using WebRTC VAD."""
        if self._vad is None:
            # Fallback to simple energy-based detection
            return await self._simple_process(audio_data)
            
        try:
            # WebRTC VAD expects 16-bit mono audio at specific sample rates
            if len(audio_data) < 160:  # Minimum frame size
                return self.state
                
            is_speech = self._vad.is_speech(audio_data, self._sample_rate)
            
            if is_speech:
                self.state = VADState.SPEAKING
                self.silence_counter = 0
                self._audio_buffer.append(audio_data)
            else:
                self.silence_counter += 1
                # Transition to silent after sustained silence
                threshold = max(1, int(self.config.silence_duration_ms / self._frame_duration_ms))
                if self.silence_counter > threshold and self.state == VADState.SPEAKING:
                    self.state = VADState.SILENT
                    
            return self.state
            
        except Exception as e:
            logger.error(f"VAD processing error: {e}")
            return self.state
            
    async def _simple_process(self, audio_data: bytes) -> VADState:
        """Fallback energy-based VAD."""
        if len(audio_data) < 2:
            return self.state
            
        # Calculate RMS energy
        samples = np.frombuffer(audio_data, dtype=np.int16)
        rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
        
        threshold = 500 * (1.0 - self.config.vad_sensitivity)
        
        if rms > threshold:
            self.state = VADState.SPEAKING
            self.silence_counter = 0
        else:
            self.silence_counter += 1
            if self.silence_counter > (self.config.silence_duration_ms / 100):
                self.state = VADState.SILENT
                
        return self.state
        
    async def reset(self):
        """Reset VAD state."""
        self.state = VADState.SILENT
        self.silence_counter = 0
        self._audio_buffer = []
        
    def get_speech_buffer(self) -> bytes:
        """Get accumulated speech audio buffer."""
        buffer = b''.join(self._audio_buffer)
        self._audio_buffer = []
        return buffer


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
    Supports both openai-whisper (Linux/Mac) and whispercpp (Windows).
    """
    
    def __init__(self, config: VoiceConfig, model_path: Optional[str] = None, use_cpp: bool = False):
        self.config = config
        self.model_path = model_path
        self._model = None
        self.use_cpp = use_cpp  # Use whisper.cpp on Windows
        
    async def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            try:
                if self.use_cpp:
                    # Try whisper.cpp for Windows
                    import whispercpp
                    self._model = whispercpp.Whisper(model=self.model_path or "base")
                    logger.info(f"Whisper.cpp model loaded: {self.model_path or 'base'}")
                else:
                    # Try openai-whisper for Linux/Mac
                    import whisper
                    self._model = whisper.load_model(self.model_path or "base")
                    logger.info("Whisper model loaded successfully")
            except ImportError as e:
                logger.warning(f"Whisper not installed ({e}), using stub implementation")
                self._model = "stub"
                
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio to text."""
        await self._load_model()
        
        if self._model == "stub":
            # Stub implementation for when whisper is not available
            logger.debug("Using STT stub - no transcription performed")
            return ""
            
        try:
            import tempfile
            import wave
            import struct
            
            # Create proper WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = Path(f.name)
                
            # Write WAV header
            with wave.open(str(temp_path), 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.config.sample_rate)
                wav_file.writeframes(audio_data)
            
            # Transcribe based on backend
            if self.use_cpp:
                # whisper.cpp expects raw audio samples as numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                result = self._model.transcribe(audio_array)
                text = result.get('text', '') if isinstance(result, dict) else str(result)
            else:
                # openai-whisper expects file path
                result = self._model.transcribe(str(temp_path))
                text = result.get("text", "")
            
            # Cleanup
            temp_path.unlink(missing_ok=True)
            return text.strip()
            
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

class WindowsSAPI5TTS(BaseTTS):
    """
    Windows SAPI5 Text-to-Speech implementation using pyttsx3.
    Provides native Windows TTS with voice selection.
    """
    
    def __init__(self, config: VoiceConfig, voice_name: Optional[str] = None, rate: int = 150):
        self.config = config
        self.voice_name = voice_name
        self.rate = rate
        self._engine = None
        
    def _get_engine(self):
        """Lazy load pyttsx3 engine."""
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', self.rate)
                
                if self.voice_name:
                    voices = self._engine.getProperty('voices')
                    for voice in voices:
                        if self.voice_name.lower() in voice.name.lower():
                            self._engine.setProperty('voice', voice.id)
                            break
                            
                logger.info("pyttsx3 TTS engine initialized")
            except ImportError:
                logger.warning("pyttsx3 not available, TTS disabled")
                self._engine = "stub"
            except Exception as e:
                logger.error(f"Failed to initialize TTS engine: {e}")
                self._engine = "stub"
        return self._engine
        
    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech - returns empty bytes as this is fire-and-play."""
        logger.debug(f"TTS requested for {len(text)} chars (fire-and-play)")
        return b""
        
    async def synthesize_to_file(self, text: str, output_path: Path) -> Path:
        """Synthesize speech and save to file."""
        engine = self._get_engine()
        
        if engine == "stub":
            logger.warning("TTS stub - cannot save to file")
            return output_path
            
        try:
            # pyttsx3 doesn't support direct file save, so we use subprocess
            # For proper file output on Windows, would need SAPI directly
            await self.speak(text)
            logger.info(f"TTS spoken: {text[:50]}...")
            return output_path
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return output_path
        
    async def speak(self, text: str) -> bool:
        """Speak text using pyttsx3."""
        engine = self._get_engine()
        
        if engine == "stub":
            return False
            
        try:
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception as e:
            logger.error(f"Speech playback failed: {e}")
            return False


class SystemTTS(BaseTTS):
    """
    System-native Text-to-Speech implementation.
    Uses platform-specific TTS engines.
    """
    
    def __init__(self, config: VoiceConfig, voice: Optional[str] = None):
        self.config = config
        self.voice = voice
        self._use_pyttsx3 = False
        
        # Try to use pyttsx3 on Windows for better control
        import platform
        if platform.system() == "Windows":
            try:
                import pyttsx3
                self._use_pyttsx3 = True
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', 150)
                if voice:
                    voices = self._engine.getProperty('voices')
                    for v in voices:
                        if voice.lower() in v.name.lower():
                            self._engine.setProperty('voice', v.id)
                            break
                logger.info("Windows TTS initialized with pyttsx3")
            except ImportError:
                logger.info("Using PowerShell TTS fallback")
        
    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech - returns empty bytes as this is fire-and-play."""
        logger.debug(f"TTS requested for {len(text)} chars (fire-and-play)")
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
    Supports both PyAudio (Windows) and simple energy-based VAD (cross-platform).
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None, use_windows_audio: bool = False):
        self.config = config or VoiceConfig()
        self.use_windows_audio = use_windows_audio
        
        # Use PyAudioVAD if available and requested
        if use_windows_audio:
            try:
                self.vad = PyAudioVAD(self.config)
                logger.info("Using PyAudio/WebRTC VAD")
            except Exception as e:
                logger.warning(f"PyAudio VAD not available ({e}), using SimpleVAD")
                self.vad = SimpleVAD(self.config)
        else:
            self.vad = SimpleVAD(self.config)
            
        # Use whisper.cpp on Windows, openai-whisper elsewhere
        import platform
        self.stt = WhisperSTT(
            self.config, 
            use_cpp=(platform.system() == "Windows")
        )
        
        # Use pyttsx3 TTS on Windows
        if platform.system() == "Windows":
            self.tts = WindowsSAPI5TTS(self.config)
        else:
            self.tts = SystemTTS(self.config)
            
        self._is_listening = False
        self._speech_callback: Optional[Callable[[str], None]] = None
        self._audio_buffer: List[bytes] = []
        
    async def start_listening(self, callback: Callable[[str], None]):
        """Start listening for speech and call callback with transcribed text."""
        self._is_listening = True
        self._speech_callback = callback
        self._audio_buffer = []
        logger.info("Voice processor started listening")
        # In production, this would start an audio capture loop using PyAudio
        
    async def stop_listening(self):
        """Stop listening."""
        self._is_listening = False
        await self.vad.reset()
        self._audio_buffer = []
        logger.info("Voice processor stopped listening")
        
    async def process_voice_input(self, audio_data: bytes) -> Optional[str]:
        """Process incoming audio and return transcription if speech detected."""
        if not self._is_listening:
            return None
            
        state = await self.vad.process_audio(audio_data)
        
        if state == VADState.SPEAKING:
            # Buffer audio for transcription
            self._audio_buffer.append(audio_data)
        elif state == VADState.SILENT and self._audio_buffer:
            # Transition from speaking to silent - transcribe buffered audio
            if len(self._audio_buffer) > 0:
                combined_audio = b''.join(self._audio_buffer)
                self._audio_buffer = []
                
                # Transcribe the buffered speech
                text = await self.stt.transcribe(combined_audio)
                
                if text and self._speech_callback:
                    await self._speech_callback(text)
                return text
                
        return None
        
    async def speak_text(self, text: str) -> bool:
        """Convert text to speech and play it."""
        return await self.tts.speak(text)
        
    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio data to text."""
        return await self.stt.transcribe(audio_data)
        
    def get_vad_state(self) -> str:
        """Get current VAD state."""
        return self.vad.state
        
    async def start_voice_session(self) -> str:
        """
        Start a voice session and return session ID.
        This is a placeholder for WebSocket-based real-time voice sessions.
        """
        import uuid
        session_id = str(uuid.uuid4())
        logger.info(f"Voice session started: {session_id}")
        return session_id
        
    async def end_voice_session(self, session_id: str):
        """End a voice session."""
        await self.stop_listening()
        logger.info(f"Voice session ended: {session_id}")


# Factory function
def get_voice_processor(config: Optional[VoiceConfig] = None, use_windows_audio: bool = False) -> VoiceProcessor:
    """Create a voice processor instance."""
    return VoiceProcessor(config, use_windows_audio)
