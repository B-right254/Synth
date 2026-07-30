"""
Ollama Cloud Adapter Service
Handles communication with Ollama instances for LLM inference.
Supports local and remote endpoints, streaming, and model management.
"""
import httpx
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class OllamaConfig(BaseModel):
    """Configuration for Ollama connection."""
    base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    default_model: str = Field(default="llama3", description="Default model to use")
    timeout: float = Field(default=120.0, description="Request timeout in seconds")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates for remote endpoints")

class ChatMessage(BaseModel):
    """Represents a chat message."""
    role: str  # "system", "user", "assistant"
    content: str

class OllamaResponse(BaseModel):
    """Standardized response from Ollama."""
    model: str
    content: str
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None

class OllamaAdapter:
    """
    Adapter for interacting with Ollama API.
    Handles chat completions, model listing, and streaming.
    """
    
    def __init__(self, config: OllamaConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout),
            verify=config.verify_ssl
        )
        
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
        
    async def health_check(self) -> bool:
        """Check if Ollama instance is reachable."""
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
            
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models."""
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
            
    async def chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> OllamaResponse:
        """
        Send a chat completion request.
        
        Args:
            messages: List of chat messages
            model: Model to use (defaults to config.default_model)
            stream: Whether to stream the response
            options: Additional model options (temperature, top_p, etc.)
            system_prompt: Optional system prompt to prepend
            
        Returns:
            OllamaResponse object
        """
        target_model = model or self.config.default_model
        
        # Prepare messages with optional system prompt
        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
            
        for msg in messages:
            final_messages.append({"role": msg.role, "content": msg.content})
            
        payload = {
            "model": target_model,
            "messages": final_messages,
            "stream": stream
        }
        
        if options:
            payload["options"] = options
            
        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            
            if stream:
                # For non-streaming call, we just return the first chunk or aggregate
                # This method is for non-streaming primarily, see chat_stream for streaming
                pass
                
            data = response.json()
            return OllamaResponse(**data)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Ollama: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Chat request failed: {e}")
            raise
            
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion response.
        
        Yields:
            Content chunks as strings
        """
        target_model = model or self.config.default_model
        
        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
            
        for msg in messages:
            final_messages.append({"role": msg.role, "content": msg.content})
            
        payload = {
            "model": target_model,
            "messages": final_messages,
            "stream": True
        }
        
        if options:
            payload["options"] = options
            
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Streaming chat failed: {e}")
            raise
            
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Simple generation endpoint (non-chat).
        Useful for single-turn tasks.
        """
        target_model = model or self.config.default_model
        
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False
        }
        
        if system:
            payload["system"] = system
            
        if options:
            payload["options"] = options
            
        try:
            response = await self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            logger.error(f"Generate request failed: {e}")
            raise

# Factory function for dependency injection
def get_ollama_adapter() -> OllamaAdapter:
    """Create an Ollama adapter with default configuration."""
    config = OllamaConfig()
    return OllamaAdapter(config)
