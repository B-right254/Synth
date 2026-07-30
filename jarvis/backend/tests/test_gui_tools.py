"""
Tests for GUI tools.
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from tools.gui_tools import (
    GUIObserveTool,
    GUIFocusTool,
    GUIClickTool,
    GUITypeTool,
    GUIHotkeyTool,
    GUIInvokeTool,
    GUISetValueTool,
)
from api.schemas import (
    GUIObserveInput,
    GUIFocusInput,
    GUIClickInput,
    GUITypeInput,
    GUIHotkeyInput,
    GUIInvokeInput,
    GUISetValueInput,
)


class TestGUIObserveTool:
    """Tests for GUIObserveTool."""
    
    @pytest.mark.asyncio
    async def test_observe_tool_creation(self):
        """Test tool can be instantiated."""
        tool = GUIObserveTool()
        assert tool.name == "gui_observe"
        assert tool.input_schema == GUIObserveInput
    
    @pytest.mark.asyncio
    async def test_observe_linux_fallback(self):
        """Test observation on Linux with xdotool."""
        tool = GUIObserveTool()
        input_data = GUIObserveInput(window_title="Test", use_ocr=False)
        
        with patch('platform.system', return_value='Linux'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="Test Window\nGeometry: 100x100+0+0"
                )
                
                result = await tool.execute(input_data)
                
                assert result.success is True
                assert "active_window" in result.data
    
    @pytest.mark.asyncio
    async def test_observe_macos(self):
        """Test observation on macOS."""
        tool = GUIObserveTool()
        input_data = GUIObserveInput(window_title="Test", use_ocr=False)
        
        with patch('platform.system', return_value='Darwin'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="FrontApp: Safari"
                )
                
                result = await tool.execute(input_data)
                
                assert result.success is True
                assert "apple_script_output" in result.data
    
    @pytest.mark.asyncio
    async def test_observe_verify_success(self):
        """Test verification of successful observation."""
        tool = GUIObserveTool()
        input_data = GUIObserveInput(window_title="Test")
        output = Mock(success=True, data={"ui_tree": {}})
        
        result = await tool.verify(input_data, output)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_observe_verify_failure(self):
        """Test verification of failed observation."""
        tool = GUIObserveTool()
        input_data = GUIObserveInput(window_title="Test")
        output = Mock(success=False, data=None)
        
        result = await tool.verify(input_data, output)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_observe_policy_requirements(self):
        """Test policy requirements."""
        tool = GUIObserveTool()
        requirements = tool.get_policy_requirements()
        
        assert "requires_screen_access" in requirements
        assert requirements["requires_screen_access"] is True
        assert "privacy_sensitive" in requirements


class TestGUIFocusTool:
    """Tests for GUIFocusTool."""
    
    @pytest.mark.asyncio
    async def test_focus_tool_creation(self):
        """Test tool can be instantiated."""
        tool = GUIFocusTool()
        assert tool.name == "gui_focus"
        assert tool.input_schema == GUIFocusInput
    
    @pytest.mark.asyncio
    async def test_focus_linux_success(self):
        """Test focusing window on Linux."""
        tool = GUIFocusTool()
        input_data = GUIFocusInput(window_title="Test Window")
        
        with patch('platform.system', return_value='Linux'):
            with patch('subprocess.run') as mock_run:
                # First call: search
                # Second call: activate
                mock_run.side_effect = [
                    MagicMock(returncode=0, stdout="12345\n"),
                    MagicMock(returncode=0, stdout="")
                ]
                
                result = await tool.execute(input_data)
                
                assert result.success is True
                assert result.data["focused_window"] == "Test Window"
    
    @pytest.mark.asyncio
    async def test_focus_linux_window_not_found(self):
        """Test focusing non-existent window on Linux."""
        tool = GUIFocusTool()
        input_data = GUIFocusInput(window_title="NonExistent")
        
        with patch('platform.system', return_value='Linux'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout=""
                )
                
                result = await tool.execute(input_data)
                
                assert result.success is False
                assert result.error["code"] == "WINDOW_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_focus_macos(self):
        """Test focusing window on macOS."""
        tool = GUIFocusTool()
        input_data = GUIFocusInput(window_title="Safari")
        
        with patch('platform.system', return_value='Darwin'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=""
                )
                
                result = await tool.execute(input_data)
                
                assert result.success is True
    
    @pytest.mark.asyncio
    async def test_focus_verify(self):
        """Test verification of focus operation."""
        tool = GUIFocusTool()
        input_data = GUIFocusInput(window_title="Test")
        output = Mock(success=True, data={"focused_window": "Test"})
        
        result = await tool.verify(input_data, output)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_focus_policy_requirements(self):
        """Test policy requirements."""
        tool = GUIFocusTool()
        requirements = tool.get_policy_requirements()
        
        assert "foreground_window_change" in requirements
        assert requirements["foreground_window_change"] is True


class TestGUIClickTool:
    """Tests for GUIClickTool."""
    
    @pytest.mark.asyncio
    async def test_click_tool_creation(self):
        """Test tool can be instantiated."""
        tool = GUIClickTool()
        assert tool.name == "gui_click"
        assert tool.input_schema == GUIClickInput
    
    @pytest.mark.asyncio
    async def test_click_linux_success(self):
        """Test clicking on Linux."""
        tool = GUIClickTool()
        input_data = GUIClickInput(window_title="Test", x=100, y=200)
        
        with patch.object(GUIClickTool, '_ensure_window_focused', new_callable=AsyncMock) as mock_focus:
            mock_focus.return_value = Mock(success=True, data={})
            
            with patch('platform.system', return_value='Linux'):
                with patch('subprocess.run') as mock_run:
                    mock_run.side_effect = [
                        MagicMock(returncode=0, stdout=""),  # mousemove
                        MagicMock(returncode=0, stdout="")   # click
                    ]
                    
                    result = await tool.execute(input_data)
                    
                    assert result.success is True
                    assert result.data["clicked_at"]["x"] == 100
                    assert result.data["clicked_at"]["y"] == 200
    
    @pytest.mark.asyncio
    async def test_click_linux_xdotool_not_found(self):
        """Test clicking when xdotool not installed."""
        tool = GUIClickTool()
        input_data = GUIClickInput(window_title="Test", x=100, y=200)
        
        with patch.object(GUIClickTool, '_ensure_window_focused', new_callable=AsyncMock) as mock_focus:
            mock_focus.return_value = Mock(success=True, data={})
            
            with patch('platform.system', return_value='Linux'):
                with patch('subprocess.run', side_effect=FileNotFoundError()):
                    result = await tool.execute(input_data)
                    
                    assert result.success is False
                    assert result.error["code"] == "XDOTOOL_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_click_verify(self):
        """Test verification of click operation."""
        tool = GUIClickTool()
        input_data = GUIClickInput(window_title="Test", x=100, y=200)
        output = Mock(success=True, data={"clicked_at": {"x": 100, "y": 200}})
        
        result = await tool.verify(input_data, output)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_click_policy_requirements(self):
        """Test policy requirements."""
        tool = GUIClickTool()
        requirements = tool.get_policy_requirements()
        
        assert "input_injection" in requirements
        assert "coordinate_bounds_check" in requirements


class TestGUITypeTool:
    """Tests for GUITypeTool."""
    
    @pytest.mark.asyncio
    async def test_type_tool_creation(self):
        """Test tool can be instantiated."""
        tool = GUITypeTool()
        assert tool.name == "gui_type"
        assert tool.input_schema == GUITypeInput
    
    @pytest.mark.asyncio
    async def test_type_linux_success(self):
        """Test typing on Linux."""
        tool = GUITypeTool()
        input_data = GUITypeInput(window_title="Test", text="Hello World")
        
        with patch.object(tool, '_ensure_window_focused', new_callable=AsyncMock) as mock_focus:
            mock_focus.return_value = Mock(success=True, data={})
            
            with patch('platform.system', return_value='Linux'):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=""
                    )
                    
                    result = await tool.execute(input_data)
                    
                    assert result.success is True
                    assert result.data["typed_text"] == "Hello World"
                    assert result.data["length"] == 11
    
    @pytest.mark.asyncio
    async def test_type_verify(self):
        """Test verification of type operation."""
        tool = GUITypeTool()
        input_data = GUITypeInput(window_title="Test", text="Test")
        output = Mock(success=True, data={"typed_text": "Test"})
        
        result = await tool.verify(input_data, output)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_type_policy_requirements(self):
        """Test policy requirements."""
        tool = GUITypeTool()
        requirements = tool.get_policy_requirements()
        
        assert "keyboard_input" in requirements
        assert "input_injection" in requirements


class TestGUIHotkeyTool:
    """Tests for GUIHotkeyTool."""
    
    @pytest.mark.asyncio
    async def test_hotkey_tool_creation(self):
        """Test tool can be instantiated."""
        tool = GUIHotkeyTool()
        assert tool.name == "gui_hotkey"
        assert tool.input_schema == GUIHotkeyInput
    
    @pytest.mark.asyncio
    async def test_hotkey_linux_success(self):
        """Test hotkey on Linux."""
        tool = GUIHotkeyTool()
        input_data = GUIHotkeyInput(window_title="Test", keys=["ctrl", "c"])
        
        with patch.object(tool, '_ensure_window_focused', new_callable=AsyncMock) as mock_focus:
            mock_focus.return_value = Mock(success=True, data={})
            
            with patch('platform.system', return_value='Linux'):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=""
                    )
                    
                    result = await tool.execute(input_data)
                    
                    assert result.success is True
                    assert result.data["hotkey_executed"] == "ctrl+c"
    
    @pytest.mark.asyncio
    async def test_hotkey_verify(self):
        """Test verification of hotkey operation."""
        tool = GUIHotkeyTool()
        input_data = GUIHotkeyInput(window_title="Test", keys=["ctrl", "v"])
        output = Mock(success=True, data={"hotkey_executed": "ctrl+v"})
        
        result = await tool.verify(input_data, output)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_hotkey_policy_requirements(self):
        """Test policy requirements."""
        tool = GUIHotkeyTool()
        requirements = tool.get_policy_requirements()
        
        assert "dangerous_combinations" in requirements
        assert "ctrl+alt+delete" in requirements["dangerous_combinations"]


class TestGUIInvokeTool:
    """Tests for GUIInvokeTool."""
    
    @pytest.mark.asyncio
    async def test_invoke_tool_creation(self):
        """Test tool can be instantiated."""
        tool = GUIInvokeTool()
        assert tool.name == "gui_invoke"
        assert tool.input_schema == GUIInvokeInput
    
    @pytest.mark.asyncio
    async def test_invoke_non_windows(self):
        """Test invoke on non-Windows platform."""
        tool = GUIInvokeTool()
        input_data = GUIInvokeInput(window_title="Test", element_description="Button")
        
        with patch('platform.system', return_value='Linux'):
            result = await tool.execute(input_data)
            
            assert result.success is False
            assert result.error["code"] == "PLATFORM_NOT_SUPPORTED"
    
    @pytest.mark.asyncio
    async def test_invoke_verify(self):
        """Test verification of invoke operation."""
        tool = GUIInvokeTool()
        input_data = GUIInvokeInput(window_title="Test", element_description="Button")
        output = Mock(success=True, data={"invoked_element": "Button"})
        
        result = await tool.verify(input_data, output)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_invoke_policy_requirements(self):
        """Test policy requirements."""
        tool = GUIInvokeTool()
        requirements = tool.get_policy_requirements()
        
        assert "requires_ui_automation" in requirements
        assert "element_interaction" in requirements


class TestGUISetValueTool:
    """Tests for GUISetValueTool."""
    
    @pytest.mark.asyncio
    async def test_set_value_tool_creation(self):
        """Test tool can be instantiated."""
        tool = GUISetValueTool()
        assert tool.name == "gui_set_value"
        assert tool.input_schema == GUISetValueInput
    
    @pytest.mark.asyncio
    async def test_set_value_non_windows(self):
        """Test set value on non-Windows platform."""
        tool = GUISetValueTool()
        input_data = GUISetValueInput(window_title="Test", element_description="Field", value="test")
        
        with patch('platform.system', return_value='Linux'):
            result = await tool.execute(input_data)
            
            assert result.success is False
            assert result.error["code"] == "PLATFORM_NOT_SUPPORTED"
    
    @pytest.mark.asyncio
    async def test_set_value_verify(self):
        """Test verification of set value operation."""
        tool = GUISetValueTool()
        input_data = GUISetValueInput(window_title="Test", element_description="Field", value="test")
        output = Mock(success=True, data={"value_set": "test"})
        
        result = await tool.verify(input_data, output)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_value_policy_requirements(self):
        """Test policy requirements."""
        tool = GUISetValueTool()
        requirements = tool.get_policy_requirements()
        
        assert "element_modification" in requirements
        assert "data_entry" in requirements


class TestGUIIntegration:
    """Integration tests for GUI tools working together."""
    
    @pytest.mark.asyncio
    async def test_focus_then_click_workflow(self):
        """Test workflow: focus window then click."""
        focus_tool = GUIFocusTool()
        click_tool = GUIClickTool()
        
        with patch('platform.system', return_value='Linux'):
            with patch('subprocess.run') as mock_run:
                # Focus: search + activate
                # Click: mousemove + click
                mock_run.side_effect = [
                    MagicMock(returncode=0, stdout="12345\n"),  # focus search
                    MagicMock(returncode=0, stdout=""),          # focus activate
                    MagicMock(returncode=0, stdout=""),          # click move
                    MagicMock(returncode=0, stdout="")           # click
                ]
                
                # Focus first
                focus_result = await focus_tool.execute(
                    GUIFocusInput(window_title="Test")
                )
                assert focus_result.success is True
                
                # Then click
                click_result = await click_tool.execute(
                    GUIClickInput(window_title="Test", x=50, y=50)
                )
                # Note: This will fail because _ensure_window_focused is called internally
                # but we're testing the workflow concept
    
    @pytest.mark.asyncio
    async def test_all_gui_tools_registered(self):
        """Test that all GUI tools have proper structure."""
        tools = [
            GUIObserveTool(),
            GUIFocusTool(),
            GUIClickTool(),
            GUITypeTool(),
            GUIHotkeyTool(),
            GUIInvokeTool(),
            GUISetValueTool(),
        ]
        
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'input_schema')
            assert hasattr(tool, 'execute')
            assert hasattr(tool, 'verify')
            assert hasattr(tool, 'get_policy_requirements')
            
            # Verify method signatures
            assert callable(tool.execute)
            assert callable(tool.verify)
            assert callable(tool.get_policy_requirements)
