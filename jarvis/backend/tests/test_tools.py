"""
Comprehensive unit tests for JARVIS tool framework
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os
import tempfile
import shutil

from tools.executor import ToolExecutor, BaseTool, ToolOutput
from pydantic import BaseModel


class MockInput(BaseModel):
    """Mock input schema for testing"""
    value: str = ""


class MockTool(BaseTool):
    """Mock tool for testing"""
    name = "mock_tool"
    description = "A mock tool for testing"
    input_schema = MockInput
    
    async def execute(self, input_data: BaseModel) -> ToolOutput:
        return ToolOutput(success=True, data={"result": "success"})
    
    async def verify(self, input_data: BaseModel, output: ToolOutput) -> bool:
        return True
    
    def get_policy_requirements(self) -> dict:
        return {"risk_level": "low", "requires_confirmation": False}


class TestToolExecutor:
    """Test the tool executor framework"""
    
    @pytest.fixture
    def executor(self):
        return ToolExecutor()
    
    @pytest.mark.asyncio
    async def test_register_and_execute_tool(self, executor):
        """Test registering and executing a tool"""
        tool = MockTool()
        executor.register_tool(tool)
        
        result = await executor.execute_tool("mock_tool", {"value": "test"})
        
        assert result.success is True
        assert result.data == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, executor):
        """Test executing a non-existent tool"""
        result = await executor.execute_tool("nonexistent_tool", {})
        
        assert result.success is False
        assert "not found" in result.error["message"].lower()
    
    @pytest.mark.asyncio
    async def test_execute_with_invalid_input(self, executor):
        """Test tool execution with invalid input"""
        tool = MockTool()
        executor.register_tool(tool)
        
        # Empty input should work since value has default
        result = await executor.execute_tool("mock_tool", {})
        
        assert result.success is True  # Mock tool succeeds with empty input
    
    @pytest.mark.asyncio
    async def test_list_tools(self, executor):
        """Test listing available tools"""
        tool = MockTool()
        executor.register_tool(tool)
        
        tools = executor.list_tools()
        
        assert len(tools) == 1
        assert "mock_tool" in tools
    
    @pytest.mark.asyncio
    async def test_get_tool(self, executor):
        """Test getting a tool by name"""
        tool = MockTool()
        executor.register_tool(tool)
        
        retrieved = executor.get_tool("mock_tool")
        
        assert retrieved is not None
        assert retrieved.name == "mock_tool"
        
        # Non-existent tool
        assert executor.get_tool("nonexistent") is None


class TestSystemTools:
    """Test system-related tools"""
    
    @pytest.fixture
    def system_time_tool(self):
        from tools.system_tools import SystemTimeTool
        return SystemTimeTool()
    
    @pytest.fixture
    def system_battery_tool(self):
        from tools.system_tools import SystemBatteryTool
        return SystemBatteryTool()
    
    @pytest.fixture
    def system_disk_tool(self):
        from tools.system_tools import SystemDiskTool
        return SystemDiskTool()
    
    @pytest.fixture
    def system_processes_tool(self):
        from tools.system_tools import SystemProcessesTool
        return SystemProcessesTool()
    
    @pytest.fixture
    def system_active_window_tool(self):
        from tools.system_tools import SystemActiveWindowTool
        return SystemActiveWindowTool()
    
    @pytest.mark.asyncio
    async def test_get_time(self, system_time_tool):
        """Test getting current time"""
        from api.schemas import SystemTimeInput
        result = await system_time_tool.execute(SystemTimeInput())
        
        assert result.success is True
        assert "datetime" in result.data or "time" in result.data
        assert "timezone" in result.data
    
    @pytest.mark.asyncio
    async def test_get_battery_status_no_battery(self, system_battery_tool):
        """Test battery status when no battery is present"""
        from api.schemas import SystemBatteryInput
        with patch('psutil.sensors_battery', return_value=None):
            result = await system_battery_tool.execute(SystemBatteryInput())
            
            assert result.success is True
            assert result.data.get("available") is False
    
    @pytest.mark.asyncio
    async def test_get_disk_usage(self, system_disk_tool):
        """Test disk usage retrieval"""
        from api.schemas import SystemDiskInput
        result = await system_disk_tool.execute(SystemDiskInput(path="/"))
        
        assert result.success is True
        assert "total_gb" in result.data or "total" in result.data
        assert "used_gb" in result.data or "used" in result.data
        assert "free_gb" in result.data or "free" in result.data
    
    @pytest.mark.asyncio
    async def test_list_processes(self, system_processes_tool):
        """Test listing processes"""
        from api.schemas import SystemProcessesInput
        result = await system_processes_tool.execute(SystemProcessesInput(limit=5))
        
        assert result.success is True
        assert isinstance(result.data, dict)
        assert "processes" in result.data
        assert isinstance(result.data["processes"], list)
        assert len(result.data["processes"]) <= 5
        if result.data["processes"]:
            assert "pid" in result.data["processes"][0]
            assert "name" in result.data["processes"][0]
    
    @pytest.mark.asyncio
    async def test_get_active_window_linux(self, system_active_window_tool):
        """Test getting active window on Linux"""
        from api.schemas import SystemActiveWindowInput
        result = await system_active_window_tool.execute(SystemActiveWindowInput())
        
        # On Linux without GUI, should return unavailable or succeed with limited info
        assert result.success is True  # Tool should not fail, just report unavailability


class TestFileTools:
    """Test file system tools"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests"""
        dirpath = tempfile.mkdtemp()
        yield dirpath
        shutil.rmtree(dirpath)
    
    @pytest.mark.asyncio
    async def test_list_directory(self, temp_dir):
        """Test listing directory contents"""
        from tools.file_tools import FileListTool
        from api.schemas import FileListInput
        
        tool = FileListTool()
        # Create test files
        os.makedirs(os.path.join(temp_dir, "subdir"))
        with open(os.path.join(temp_dir, "test.txt"), "w") as f:
            f.write("test content")
        
        result = await tool.execute(FileListInput(path=temp_dir))
        
        assert result.success is True
        assert "items" in result.data or "entries" in result.data
        items = result.data.get("items", result.data.get("entries", []))
        names = [e["name"] for e in items]
        assert "test.txt" in names
        assert "subdir" in names
    
    @pytest.mark.asyncio
    async def test_read_file(self, temp_dir):
        """Test reading a file"""
        from tools.file_tools import FileReadTool
        from api.schemas import FileReadInput
        
        tool = FileReadTool()
        test_content = "Hello, World!"
        file_path = os.path.join(temp_dir, "test.txt")
        
        with open(file_path, "w") as f:
            f.write(test_content)
        
        result = await tool.execute(FileReadInput(path=file_path))
        
        assert result.success is True
        assert result.data["content"] == test_content
        assert result.data["size"] == len(test_content)
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading a non-existent file"""
        from tools.file_tools import FileReadTool
        from api.schemas import FileReadInput
        
        tool = FileReadTool()
        result = await tool.execute(FileReadInput(path="/nonexistent/path/file.txt"))
        
        assert result.success is False
        assert "not found" in result.error.get("message", "").lower()
    
    @pytest.mark.asyncio
    async def test_create_file(self, temp_dir):
        """Test creating a new file"""
        from tools.file_tools import FileCreateTool
        from api.schemas import FileCreateInput
        
        tool = FileCreateTool()
        file_path = os.path.join(temp_dir, "newfile.txt")
        result = await tool.execute(FileCreateInput(path=file_path, content="initial content"))
        
        assert result.success is True
        assert os.path.exists(file_path)
    
    @pytest.mark.asyncio
    async def test_create_existing_file(self, temp_dir):
        """Test creating a file that already exists"""
        from tools.file_tools import FileCreateTool
        from api.schemas import FileCreateInput
        
        tool = FileCreateTool()
        # Create the file first
        file_path = os.path.join(temp_dir, "existing.txt")
        with open(file_path, "w") as f:
            f.write("existing")
        
        result = await tool.execute(FileCreateInput(path=file_path, content="new content"))
        
        assert result.success is False
        assert "exists" in result.error.get("message", "").lower()
    
    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir):
        """Test writing to a file"""
        from tools.file_tools import FileWriteTool
        from api.schemas import FileWriteInput
        
        tool = FileWriteTool()
        file_path = os.path.join(temp_dir, "write_test.txt")
        
        # Write initially
        result1 = await tool.execute(FileWriteInput(path=file_path, content="first line\n"))
        assert result1.success is True
        
        # Append
        result2 = await tool.execute(FileWriteInput(path=file_path, content="second line\n", append=True))
        assert result2.success is True
        
        # Read back
        with open(file_path, "r") as f:
            content = f.read()
        
        assert "first line" in content
        assert "second line" in content
    
    @pytest.mark.asyncio
    async def test_delete_file(self, temp_dir):
        """Test deleting a file"""
        from tools.file_tools import FileDeleteTool
        from api.schemas import FileDeleteInput
        
        tool = FileDeleteTool()
        file_path = os.path.join(temp_dir, "to_delete.txt")
        
        # Create the file
        with open(file_path, "w") as f:
            f.write("to delete")
        
        result = await tool.execute(FileDeleteInput(path=file_path))
        
        assert result.success is True
        assert not os.path.exists(file_path)


class TestToolMetadata:
    """Test tool metadata and validation"""
    
    def test_tool_metadata_structure(self):
        """Verify all tools have required metadata"""
        from tools.executor import ToolExecutor
        
        executor = ToolExecutor()
        
        for tool_name in executor.list_tools():
            tool = executor.get_tool(tool_name)
            if tool:
                policy_reqs = tool.get_policy_requirements()
                assert policy_reqs is not None, f"Tool {tool_name} missing policy requirements"
                assert "risk_level" in policy_reqs
                assert policy_reqs["risk_level"] in ["low", "medium", "high", "critical"]
                assert "requires_confirmation" in policy_reqs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
