"""
Tool executor framework for JARVIS.
Executes typed tools with policy evaluation and verification.
"""

from abc import ABC, abstractmethod
from typing import Type, Dict, Any, Optional
from pydantic import BaseModel
import time

# Use absolute import instead of relative
try:
    from api.schemas import ToolOutput
except ImportError:
    # Fallback for different import contexts
    try:
        from jarvis_backend.api.schemas import ToolOutput
    except ImportError:
        # Define minimal fallback if needed
        class ToolOutput(BaseModel):
            success: bool
            data: Optional[Dict[str, Any]] = None
            error: Optional[Dict[str, Any]] = None
            evidence: Optional[Dict[str, Any]] = None
            duration_ms: int = 0


class BaseTool(ABC):
    """Base class for all tools."""
    
    name: str
    description: str
    input_schema: Type[BaseModel]
    
    @abstractmethod
    async def execute(self, input_data: BaseModel) -> ToolOutput:
        """Execute the tool with given input.
        
        Args:
            input_data: Validated input data
            
        Returns:
            ToolOutput with success/failure status and evidence
        """
        pass
    
    @abstractmethod
    async def verify(self, input_data: BaseModel, output: ToolOutput) -> bool:
        """Verify the tool execution result.
        
        Args:
            input_data: The input that was used
            output: The execution output to verify
            
        Returns:
            True if verification passed
        """
        pass
    
    @abstractmethod
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool.
        
        Returns:
            Dictionary of policy requirements
        """
        pass


class ToolExecutor:
    """Executes tools with timing and error handling."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool for execution.
        
        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a registered tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(self) -> list:
        """List all registered tools.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    async def execute_tool(
        self,
        tool_name: str,
        input_data: Dict[str, Any]
    ) -> ToolOutput:
        """Execute a tool with validated input.
        
        Args:
            tool_name: Name of the tool to execute
            input_data: Input data dictionary
            
        Returns:
            ToolOutput with execution results
            
        Raises:
            ValueError: If tool not found or input validation fails
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolOutput(
                success=False,
                error={"code": "TOOL_NOT_FOUND", "message": f"Tool '{tool_name}' not found"},
                duration_ms=0
            )
        
        # Validate input
        try:
            validated_input = tool.input_schema(**input_data)
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "INVALID_INPUT", "message": str(e)},
                duration_ms=0
            )
        
        # Execute with timing
        start_time = time.time()
        try:
            output = await tool.execute(validated_input)
            duration_ms = int((time.time() - start_time) * 1000)
            output.duration_ms = duration_ms
            
            # Verify if successful
            if output.success:
                verified = await tool.verify(validated_input, output)
                if not verified:
                    output.success = False
                    output.error = {"code": "VERIFICATION_FAILED", "message": "Post-execution verification failed"}
            
            return output
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolOutput(
                success=False,
                error={"code": "EXECUTION_ERROR", "message": str(e)},
                duration_ms=duration_ms
            )
