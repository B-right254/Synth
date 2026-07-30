"""
Ollama Cloud adapter for JARVIS.
Handles authentication, model selection, and tool calls.
"""

import httpx
from typing import List, Dict, Any, Optional
from ..core.config import settings


class OllamaCloudAdapter:
    """Adapter for Ollama Cloud API."""

    def __init__(self):
        self.base_url = settings.ollama_cloud_base_url
        self.api_key = settings.ollama_api_key
        self.selected_model = settings.selected_model
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with authentication."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def check_health(self) -> bool:
        """Check if Ollama Cloud is accessible with current credentials."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from Ollama Cloud."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            raise RuntimeError(f"Failed to list models: {str(e)}")

    async def execute_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """Execute a tool call via Ollama Cloud.

        Args:
            messages: Conversation messages
            tools: Tool definitions in OpenAI format
            max_tokens: Maximum output tokens

        Returns:
            Model response with tool calls

        Raises:
            RuntimeError: If the request fails
        """
        try:
            client = await self._get_client()
            
            payload = {
                "model": self.selected_model,
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "tool_choice": "auto",
            }

            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RuntimeError("Rate limit exceeded")
            elif e.response.status_code == 401:
                raise RuntimeError("Invalid API key")
            else:
                raise RuntimeError(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise RuntimeError(f"Request failed: {str(e)}")

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton instance
_adapter: Optional[OllamaCloudAdapter] = None


def get_adapter() -> OllamaCloudAdapter:
    """Get the Ollama Cloud adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = OllamaCloudAdapter()
    return _adapter


def format_tools_for_ollama(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format tool definitions for Ollama Cloud API.

    Args:
        tools: List of tool definitions with name, description, and input_schema

    Returns:
        List of tools in OpenAI function calling format
    """
    formatted = []
    for tool in tools:
        # Convert Pydantic schema to JSON Schema
        properties = {}
        required = []
        
        if hasattr(tool.get('input_schema'), 'model_fields'):
            for field_name, field_info in tool['input_schema'].model_fields.items():
                prop = {
                    "type": "string",  # Default type
                    "description": field_info.description or "",
                }
                
                # Infer type from annotation
                if hasattr(field_info, 'annotation'):
                    ann = field_info.annotation
                    if ann == int:
                        prop["type"] = "integer"
                    elif ann == float:
                        prop["type"] = "number"
                    elif ann == bool:
                        prop["type"] = "boolean"
                    elif hasattr(ann, '__origin__') and ann.__origin__ is list:
                        prop["type"] = "array"
                
                properties[field_name] = prop
                
                # Check if required
                if not field_info.is_required() and field_info.default is None:
                    pass  # Optional
                else:
                    required.append(field_name)

        formatted.append({
            "type": "function",
            "function": {
                "name": tool['name'],
                "description": tool['description'],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })

    return formatted
