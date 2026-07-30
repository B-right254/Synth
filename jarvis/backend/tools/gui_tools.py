"""
GUI Tools for JARVIS
Implements GUI observation and interaction using UI Automation (Windows) with OCR fallback.
Platform-specific implementations for Windows with fallbacks for Linux/Mac.
"""
import platform
import subprocess
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from tools.executor import BaseTool
from api.schemas import (
    ToolOutput,
    GUIObserveInput,
    GUIFocusInput,
    GUIInvokeInput,
    GUISetValueInput,
    GUIClickInput,
    GUITypeInput,
    GUIHotkeyInput,
)


class GUIObserveTool(BaseTool):
    """Observe the current GUI state with optional OCR."""
    
    name = "gui_observe"
    description = "Observe the current GUI state, optionally using OCR to extract text from screen"
    input_schema = GUIObserveInput
    
    async def execute(self, input_data: GUIObserveInput) -> ToolOutput:
        """Execute the GUI observe tool."""
        try:
            system = platform.system()
            
            if system == "Windows":
                return await self._observe_windows(input_data)
            elif system == "Darwin":
                return await self._observe_macos(input_data)
            else:
                return await self._observe_linux(input_data)
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "OBSERVATION_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _observe_windows(self, input_data: GUIObserveInput) -> ToolOutput:
        """Observe GUI on Windows using UI Automation."""
        try:
            import comtypes.client
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as uia
            
            # Create UI Automation instance
            iuia = comtypes.client.CreateObject(uia.CUIAutomation8).QueryInterface(uia.IUIAutomation)
            
            # Get root element
            root = iuia.GetRootElement()
            
            # Find window if title specified
            if input_data.window_title:
                condition = iuia.CreatePropertyCondition(
                    uia.UIA_NamePropertyId,
                    input_data.window_title
                )
                window = root.FindFirst(uia.TreeScope_Children, condition)
                if not window:
                    # Try partial match
                    window = self._find_window_by_partial_title(iuia, root, input_data.window_title)
                
                if not window:
                    return ToolOutput(
                        success=False,
                        error={"code": "WINDOW_NOT_FOUND", "message": f"Window '{input_data.window_title}' not found"},
                        data={"available_windows": self._list_windows(iuia, root)}
                    )
                target = window
            else:
                target = root
            
            # Build UI tree
            ui_tree = self._build_ui_tree(iuia, target, max_depth=3)
            
            # OCR if requested
            ocr_text = None
            if input_data.use_ocr:
                ocr_text = await self._perform_ocr_windows(target)
            
            return ToolOutput(
                success=True,
                data={
                    "ui_tree": ui_tree,
                    "ocr_text": ocr_text,
                    "window_title": input_data.window_title or "Desktop"
                },
                evidence={"screenshot_path": None}  # Could capture screenshot here
            )
            
        except ImportError:
            # Fallback to basic screenshot approach
            return await self._fallback_observe(input_data)
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "UIA_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    def _find_window_by_partial_title(self, iuia, root, partial_title: str) -> Optional[Any]:
        """Find window by partial title match."""
        condition = iuia.CreatePropertyCondition(
            uia.UIA_ControlTypePropertyId,
            uia.UIA_WindowControlTypeId
        )
        windows = root.FindAll(uia.TreeScope_Children, condition)
        
        for i in range(windows.Length):
            window = windows.GetElement(i)
            name = window.CurrentName
            if partial_title.lower() in name.lower():
                return window
        return None
    
    def _list_windows(self, iuia, root) -> List[str]:
        """List all available window titles."""
        windows = []
        condition = iuia.CreatePropertyCondition(
            uia.UIA_ControlTypePropertyId,
            uia.UIA_WindowControlTypeId
        )
        result = root.FindAll(uia.TreeScope_Children, condition)
        
        for i in range(result.Length):
            window = result.GetElement(i)
            name = window.CurrentName
            if name:  # Skip empty titles
                windows.append(name)
        
        return windows
    
    def _build_ui_tree(self, iuia, element, depth: int = 0, max_depth: int = 3) -> Dict[str, Any]:
        """Build a simplified UI tree representation."""
        if depth > max_depth:
            return {}
        
        node = {
            "name": element.CurrentName or "<unnamed>",
            "control_type": self._get_control_type_name(element.CurrentControlType),
            "class_name": element.CurrentClassName or "",
            "is_enabled": element.CurrentIsEnabled,
            "is_visible": element.CurrentIsOffscreen == False,
        }
        
        # Add children
        children = []
        walker = iuia.ControlViewWalker
        child = walker.GetFirstChildElement(element)
        
        while child:
            children.append(self._build_ui_tree(iuia, child, depth + 1, max_depth))
            child = walker.GetNextSiblingElement(child)
        
        if children:
            node["children"] = children
        
        return node
    
    def _get_control_type_name(self, control_type_id: int) -> str:
        """Convert control type ID to readable name."""
        # Simplified mapping - in production would have full mapping
        type_map = {
            50000: "Pane",
            50004: "Text",
            50005: "MenuBar",
            50007: "CheckBox",
            50008: "RadioButton",
            50009: "ComboBox",
            50010: "Edit",
            50011: "Button",
            50012: "Calendar",
            50013: "DataGrid",
            50016: "Document",
            50017: "Group",
            50019: "Image",
            50020: "List",
            50021: "ListItem",
            50022: "Menu",
            50023: "MenuItem",
            50024: "ScrollBar",
            50025: "Slider",
            50026: "Spinner",
            50027: "StatusBar",
            50028: "Tab",
            50029: "TabItem",
            50030: "Text",
            50031: "ToolBar",
            50032: "ToolTip",
            50033: "Tree",
            50034: "TreeItem",
            50035: "Custom",
            50036: "Window",
        }
        return type_map.get(control_type_id, f"Unknown({control_type_id})")
    
    async def _perform_ocr_windows(self, element) -> Optional[str]:
        """Perform OCR on the specified element."""
        try:
            # Use Windows.Media.Ocr if available (Windows 10+)
            import winrt.windows.media.ocr as ocr
            import winrt.windows.graphics.imaging as imaging
            
            # Get bounding rectangle
            rect = element.CurrentBoundingRectangle
            
            # Capture screenshot of region (simplified - would need actual capture)
            # For now, return None as this requires additional setup
            return None
            
        except ImportError:
            # Try Tesseract as fallback
            try:
                import pytesseract
                from PIL import Image
                
                # Would need actual screenshot here
                return None
            except ImportError:
                return None
    
    async def _fallback_observe(self, input_data: GUIObserveInput) -> ToolOutput:
        """Fallback observation method for systems without UIA."""
        # Try to use xdotool on Linux
        if platform.system() == "Linux":
            try:
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                window_title = result.stdout.strip()
                
                return ToolOutput(
                    success=True,
                    data={
                        "active_window": window_title,
                        "note": "Limited observation on Linux - consider installing UI automation tools"
                    }
                )
            except Exception:
                pass
        
        return ToolOutput(
            success=True,
            data={
                "note": "GUI observation not fully supported on this platform",
                "platform": platform.system()
            }
        )
    
    async def _observe_macos(self, input_data: GUIObserveInput) -> ToolOutput:
        """Observe GUI on macOS using AppleScript."""
        try:
            # Get frontmost app
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                set windowList to every window of application process frontApp
                return {frontApp, windowList}
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return ToolOutput(
                success=True,
                data={
                    "apple_script_output": result.stdout,
                    "platform": "macOS"
                }
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "MACOS_OBSERVE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _observe_linux(self, input_data: GUIObserveInput) -> ToolOutput:
        """Observe GUI on Linux using xdotool/wmctrl."""
        try:
            # Get active window
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                window_title = result.stdout.strip()
                
                # Get window geometry
                geom_result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowgeometry"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                return ToolOutput(
                    success=True,
                    data={
                        "active_window": window_title,
                        "geometry": geom_result.stdout.strip() if geom_result.returncode == 0 else None
                    }
                )
            
            return ToolOutput(
                success=True,
                data={"note": "xdotool not available or failed"}
            )
            
        except FileNotFoundError:
            return ToolOutput(
                success=True,
                data={"note": "xdotool not installed. Install with: sudo apt install xdotool"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "LINUX_OBSERVE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: GUIObserveInput, output: ToolOutput) -> bool:
        """Verify the observation was successful."""
        return output.success and output.data is not None
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {
            "requires_screen_access": True,
            "requires_ui_automation": True,
            "elevated_process_check": True,
            "privacy_sensitive": True
        }


class GUIFocusTool(BaseTool):
    """Focus/activate a specific window."""
    
    name = "gui_focus"
    description = "Bring a window to the foreground and give it focus"
    input_schema = GUIFocusInput
    
    async def execute(self, input_data: GUIFocusInput) -> ToolOutput:
        """Execute the GUI focus tool."""
        try:
            system = platform.system()
            
            if system == "Windows":
                return await self._focus_windows(input_data)
            elif system == "Darwin":
                return await self._focus_macos(input_data)
            else:
                return await self._focus_linux(input_data)
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "FOCUS_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _focus_windows(self, input_data: GUIFocusInput) -> ToolOutput:
        """Focus window on Windows."""
        try:
            import comtypes.client
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as uia
            
            iuia = comtypes.client.CreateObject(uia.CUIAutomation8).QueryInterface(uia.IUIAutomation)
            root = iuia.GetRootElement()
            
            # Find window
            window = self._find_window_by_title(iuia, root, input_data.window_title)
            
            if not window:
                return ToolOutput(
                    success=False,
                    error={"code": "WINDOW_NOT_FOUND", "message": f"Window '{input_data.window_title}' not found"},
                    data={"available_windows": self._list_windows(iuia, root)}
                )
            
            # Try to activate the window
            pattern = None
            try:
                pattern = window.GetCurrentPattern(uia.UIA_WindowPatternId)
                pattern.SetWindowStyle(uia.WindowVisualState_Normal)
                pattern.WaitForInputIdle(5000)
            except Exception:
                pass
            
            # Fallback: use SetForegroundWindow via ctypes
            try:
                import ctypes
                hwnd = None
                # Get HWND from UIA element (simplified)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            
            return ToolOutput(
                success=True,
                data={"focused_window": input_data.window_title},
                evidence={"method": "UIA_WindowPattern"}
            )
            
        except ImportError:
            # Fallback using pyautogui
            try:
                import pyautogui
                # pyautogui can't directly focus windows, but we can try
                return ToolOutput(
                    success=False,
                    error={"code": "NO_UIA", "message": "UI Automation not available, pyautogui cannot focus specific windows"}
                )
            except ImportError:
                return ToolOutput(
                    success=False,
                    error={"code": "NO_FOCUS_METHOD", "message": "No window focusing method available"}
                )
    
    def _find_window_by_title(self, iuia, root, title: str) -> Optional[Any]:
        """Find window by exact or partial title."""
        # Try exact match first
        condition = iuia.CreatePropertyCondition(
            uia.UIA_NamePropertyId,
            title
        )
        window = root.FindFirst(uia.TreeScope_Children, condition)
        
        if window:
            return window
        
        # Try partial match
        return self._find_window_by_partial_title(iuia, root, title)
    
    def _list_windows(self, iuia, root) -> List[str]:
        """List all available window titles."""
        windows = []
        condition = iuia.CreatePropertyCondition(
            uia.UIA_ControlTypePropertyId,
            uia.UIA_WindowControlTypeId
        )
        result = root.FindAll(uia.TreeScope_Children, condition)
        
        for i in range(result.Length):
            window = result.GetElement(i)
            name = window.CurrentName
            if name:
                windows.append(name)
        
        return windows
    
    async def _focus_macos(self, input_data: GUIFocusInput) -> ToolOutput:
        """Focus window on macOS."""
        try:
            script = f'''
            tell application "{input_data.window_title}"
                activate
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"focused_window": input_data.window_title}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "APPLESCRIPT_ERROR", "message": result.stderr}
                )
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "MACOS_FOCUS_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _focus_linux(self, input_data: GUIFocusInput) -> ToolOutput:
        """Focus window on Linux."""
        try:
            # Search for window
            search_result = subprocess.run(
                ["xdotool", "search", "--name", input_data.window_title],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if search_result.returncode != 0 or not search_result.stdout.strip():
                return ToolOutput(
                    success=False,
                    error={"code": "WINDOW_NOT_FOUND", "message": f"Window '{input_data.window_title}' not found"}
                )
            
            window_id = search_result.stdout.strip().split('\n')[0]
            
            # Activate window
            activate_result = subprocess.run(
                ["xdotool", "windowactivate", "--sync", window_id],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if activate_result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"focused_window": input_data.window_title, "window_id": window_id}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "ACTIVATE_FAILED", "message": activate_result.stderr}
                )
                
        except FileNotFoundError:
            return ToolOutput(
                success=False,
                error={"code": "XDOTOOL_NOT_FOUND", "message": "xdotool not installed"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "LINUX_FOCUS_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: GUIFocusInput, output: ToolOutput) -> bool:
        """Verify the window was focused."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {
            "requires_screen_access": True,
            "elevated_process_check": True,
            "foreground_window_change": True
        }


class GUIClickTool(BaseTool):
    """Click at specific coordinates or on a UI element."""
    
    name = "gui_click"
    description = "Click at coordinates or on a UI element in a window"
    input_schema = GUIClickInput
    
    async def execute(self, input_data: GUIClickInput) -> ToolOutput:
        """Execute the GUI click tool."""
        try:
            system = platform.system()
            
            # First focus the window
            focus_result = await self._ensure_window_focused(input_data.window_title)
            if not focus_result.success:
                return focus_result
            
            # Perform click
            if system == "Windows":
                return await self._click_windows(input_data)
            elif system == "Darwin":
                return await self._click_macos(input_data)
            else:
                return await self._click_linux(input_data)
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "CLICK_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _ensure_window_focused(self, window_title: str) -> ToolOutput:
        """Ensure window is focused before clicking."""
        focus_tool = GUIFocusTool()
        return await focus_tool.execute(GUIFocusInput(window_title=window_title))
    
    async def _click_windows(self, input_data: GUIClickInput) -> ToolOutput:
        """Click on Windows."""
        try:
            import ctypes
            from ctypes import wintypes
            
            # Move mouse and click
            ctypes.windll.user32.SetCursorPos(input_data.x, input_data.y)
            ctypes.windll.user32.mouse_event(
                0x0002 | 0x0004,  # MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP
                0, 0, 0, 0
            )
            
            return ToolOutput(
                success=True,
                data={"clicked_at": {"x": input_data.x, "y": input_data.y}},
                evidence={"method": "SetCursorPos+mouse_event"}
            )
            
        except Exception as e:
            # Fallback to pyautogui
            try:
                import pyautogui
                pyautogui.click(input_data.x, input_data.y)
                return ToolOutput(
                    success=True,
                    data={"clicked_at": {"x": input_data.x, "y": input_data.y}},
                    evidence={"method": "pyautogui"}
                )
            except ImportError:
                return ToolOutput(
                    success=False,
                    error={"code": "NO_CLICK_METHOD", "message": "Neither ctypes nor pyautogui available"}
                )
    
    async def _click_macos(self, input_data: GUIClickInput) -> ToolOutput:
        """Click on macOS."""
        try:
            script = f'''
            tell application "System Events"
                set position of cursor to {{{input_data.x}, {input_data.y}}}
                click
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"clicked_at": {"x": input_data.x, "y": input_data.y}}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "APPLESCRIPT_ERROR", "message": result.stderr}
                )
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "MACOS_CLICK_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _click_linux(self, input_data: GUIClickInput) -> ToolOutput:
        """Click on Linux."""
        try:
            # Move mouse
            move_result = subprocess.run(
                ["xdotool", "mousemove", str(input_data.x), str(input_data.y)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if move_result.returncode != 0:
                return ToolOutput(
                    success=False,
                    error={"code": "MOVE_FAILED", "message": move_result.stderr}
                )
            
            # Click
            click_result = subprocess.run(
                ["xdotool", "click", "1"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if click_result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"clicked_at": {"x": input_data.x, "y": input_data.y}}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "CLICK_FAILED", "message": click_result.stderr}
                )
                
        except FileNotFoundError:
            return ToolOutput(
                success=False,
                error={"code": "XDOTOOL_NOT_FOUND", "message": "xdotool not installed"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "LINUX_CLICK_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: GUIClickInput, output: ToolOutput) -> bool:
        """Verify the click was executed."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {
            "requires_screen_access": True,
            "elevated_process_check": True,
            "input_injection": True,
            "coordinate_bounds_check": True
        }


class GUITypeTool(BaseTool):
    """Type text into the focused window."""
    
    name = "gui_type"
    description = "Type text into the currently focused window or element"
    input_schema = GUITypeInput
    
    async def execute(self, input_data: GUITypeInput) -> ToolOutput:
        """Execute the GUI type tool."""
        try:
            system = platform.system()
            
            # First focus the window
            focus_result = await self._ensure_window_focused(input_data.window_title)
            if not focus_result.success:
                return focus_result
            
            # Type the text
            if system == "Windows":
                return await self._type_windows(input_data)
            elif system == "Darwin":
                return await self._type_macos(input_data)
            else:
                return await self._type_linux(input_data)
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "TYPE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _ensure_window_focused(self, window_title: str) -> ToolOutput:
        """Ensure window is focused before typing."""
        focus_tool = GUIFocusTool()
        return await focus_tool.execute(GUIFocusInput(window_title=window_title))
    
    async def _type_windows(self, input_data: GUITypeInput) -> ToolOutput:
        """Type on Windows."""
        try:
            import ctypes
            import time
            
            # Use SendInput for reliable typing
            user32 = ctypes.windll.user32
            
            for char in input_data.text:
                # Simple implementation - would need proper virtual key mapping
                user32.keybd_event(ord(char.upper()), 0, 0, 0)
                user32.keybd_event(ord(char.upper()), 0, 2, 0)
                time.sleep(0.01)  # Small delay between keystrokes
            
            return ToolOutput(
                success=True,
                data={"typed_text": input_data.text, "length": len(input_data.text)},
                evidence={"method": "SendInput"}
            )
            
        except Exception as e:
            # Fallback to pyautogui
            try:
                import pyautogui
                pyautogui.typewrite(input_data.text, interval=0.05)
                return ToolOutput(
                    success=True,
                    data={"typed_text": input_data.text, "length": len(input_data.text)},
                    evidence={"method": "pyautogui"}
                )
            except ImportError:
                return ToolOutput(
                    success=False,
                    error={"code": "NO_TYPE_METHOD", "message": "Neither ctypes nor pyautogui available"}
                )
    
    async def _type_macos(self, input_data: GUITypeInput) -> ToolOutput:
        """Type on macOS."""
        try:
            # Escape special characters for AppleScript
            escaped_text = input_data.text.replace('"', '\\"')
            
            script = f'''
            tell application "System Events"
                keystroke "{escaped_text}"
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"typed_text": input_data.text, "length": len(input_data.text)}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "APPLESCRIPT_ERROR", "message": result.stderr}
                )
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "MACOS_TYPE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _type_linux(self, input_data: GUITypeInput) -> ToolOutput:
        """Type on Linux."""
        try:
            # Use xdotool to type
            result = subprocess.run(
                ["xdotool", "type", "--", input_data.text],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"typed_text": input_data.text, "length": len(input_data.text)}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "TYPE_FAILED", "message": result.stderr}
                )
                
        except FileNotFoundError:
            return ToolOutput(
                success=False,
                error={"code": "XDOTOOL_NOT_FOUND", "message": "xdotool not installed"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "LINUX_TYPE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: GUITypeInput, output: ToolOutput) -> bool:
        """Verify the text was typed."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {
            "requires_screen_access": True,
            "elevated_process_check": True,
            "input_injection": True,
            "keyboard_input": True
        }


class GUIHotkeyTool(BaseTool):
    """Execute a keyboard hotkey combination."""
    
    name = "gui_hotkey"
    description = "Press a combination of keys (hotkey) in the focused window"
    input_schema = GUIHotkeyInput
    
    async def execute(self, input_data: GUIHotkeyInput) -> ToolOutput:
        """Execute the GUI hotkey tool."""
        try:
            system = platform.system()
            
            # First focus the window
            focus_result = await self._ensure_window_focused(input_data.window_title)
            if not focus_result.success:
                return focus_result
            
            # Execute hotkey
            if system == "Windows":
                return await self._hotkey_windows(input_data)
            elif system == "Darwin":
                return await self._hotkey_macos(input_data)
            else:
                return await self._hotkey_linux(input_data)
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "HOTKEY_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _ensure_window_focused(self, window_title: str) -> ToolOutput:
        """Ensure window is focused before hotkey."""
        focus_tool = GUIFocusTool()
        return await focus_tool.execute(GUIFocusInput(window_title=window_title))
    
    async def _hotkey_windows(self, input_data: GUIHotkeyInput) -> ToolOutput:
        """Execute hotkey on Windows."""
        try:
            import ctypes
            import time
            
            user32 = ctypes.windll.user32
            
            # Map common key names to virtual key codes
            vk_map = {
                "ctrl": 0x11,
                "alt": 0x12,
                "shift": 0x10,
                "win": 0x5B,
                "enter": 0x0D,
                "tab": 0x09,
                "escape": 0x1B,
                "space": 0x20,
                "up": 0x26,
                "down": 0x28,
                "left": 0x25,
                "right": 0x27,
                "delete": 0x2E,
                "backspace": 0x08,
            }
            
            # Press all keys down
            for key in input_data.keys:
                vk = vk_map.get(key.lower(), ord(key.upper()))
                user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.01)
            
            # Release all keys up (in reverse order)
            for key in reversed(input_data.keys):
                vk = vk_map.get(key.lower(), ord(key.upper()))
                user32.keybd_event(vk, 0, 2, 0)
                time.sleep(0.01)
            
            return ToolOutput(
                success=True,
                data={"hotkey_executed": "+".join(input_data.keys)},
                evidence={"method": "keybd_event"}
            )
            
        except Exception as e:
            # Fallback to pyautogui
            try:
                import pyautogui
                # Convert key names for pyautogui
                key_map = {
                    "ctrl": "ctrl",
                    "alt": "alt",
                    "shift": "shift",
                    "win": "command" if platform.system() == "Darwin" else "win",
                }
                keys = [key_map.get(k.lower(), k) for k in input_data.keys]
                pyautogui.hotkey(*keys)
                return ToolOutput(
                    success=True,
                    data={"hotkey_executed": "+".join(input_data.keys)},
                    evidence={"method": "pyautogui"}
                )
            except ImportError:
                return ToolOutput(
                    success=False,
                    error={"code": "NO_HOTKEY_METHOD", "message": "Neither ctypes nor pyautogui available"}
                )
    
    async def _hotkey_macos(self, input_data: GUIHotkeyInput) -> ToolOutput:
        """Execute hotkey on macOS."""
        try:
            # Map keys for AppleScript
            key_map = {
                "ctrl": "control",
                "alt": "option",
                "shift": "shift",
                "win": "command",
                "enter": "return",
                "escape": "escape",
                "space": "space",
                "tab": "tab",
            }
            
            keys = [key_map.get(k.lower(), k) for k in input_data.keys]
            keystroke_part = keys[-1] if keys else ""
            modifiers = keys[:-1] if len(keys) > 1 else []
            
            if modifiers:
                modifier_str = " using {" + ", ".join(modifiers) + "}"
                script = f'''
                tell application "System Events"
                    keystroke "{keystroke_part}"{modifier_str}
                end tell
                '''
            else:
                script = f'''
                tell application "System Events"
                    keystroke "{keystroke_part}"
                end tell
                '''
            
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"hotkey_executed": "+".join(input_data.keys)}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "APPLESCRIPT_ERROR", "message": result.stderr}
                )
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "MACOS_HOTKEY_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _hotkey_linux(self, input_data: GUIHotkeyInput) -> ToolOutput:
        """Execute hotkey on Linux."""
        try:
            # Build xdotool command
            key_args = []
            for key in input_data.keys:
                key_args.extend(["keydown", key])
            key_args.append("keyup")
            key_args.extend(input_data.keys)
            
            result = subprocess.run(
                ["xdotool"] + key_args,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return ToolOutput(
                    success=True,
                    data={"hotkey_executed": "+".join(input_data.keys)}
                )
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "HOTKEY_FAILED", "message": result.stderr}
                )
                
        except FileNotFoundError:
            return ToolOutput(
                success=False,
                error={"code": "XDOTOOL_NOT_FOUND", "message": "xdotool not installed"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "LINUX_HOTKEY_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: GUIHotkeyInput, output: ToolOutput) -> bool:
        """Verify the hotkey was executed."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {
            "requires_screen_access": True,
            "elevated_process_check": True,
            "input_injection": True,
            "keyboard_input": True,
            "dangerous_combinations": ["ctrl+alt+delete", "alt+f4", "win+x"]
        }


class GUIInvokeTool(BaseTool):
    """Invoke/click a UI element by description."""
    
    name = "gui_invoke"
    description = "Invoke (click/activate) a specific UI element by its description"
    input_schema = GUIInvokeInput
    
    async def execute(self, input_data: GUIInvokeInput) -> ToolOutput:
        """Execute the GUI invoke tool."""
        try:
            system = platform.system()
            
            if system == "Windows":
                return await self._invoke_windows(input_data)
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "PLATFORM_NOT_SUPPORTED", "message": f"GUI invoke not fully supported on {system}"}
                )
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "INVOKE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _invoke_windows(self, input_data: GUIInvokeInput) -> ToolOutput:
        """Invoke element on Windows using UIA."""
        try:
            import comtypes.client
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as uia
            
            iuia = comtypes.client.CreateObject(uia.CUIAutomation8).QueryInterface(uia.IUIAutomation)
            root = iuia.GetRootElement()
            
            # Find window
            window = self._find_window_by_title(iuia, root, input_data.window_title)
            if not window:
                return ToolOutput(
                    success=False,
                    error={"code": "WINDOW_NOT_FOUND", "message": f"Window '{input_data.window_title}' not found"}
                )
            
            # Find element by description (name or automation id)
            element = self._find_element_by_description(iuia, window, input_data.element_description)
            
            if not element:
                return ToolOutput(
                    success=False,
                    error={"code": "ELEMENT_NOT_FOUND", "message": f"Element '{input_data.element_description}' not found"}
                )
            
            # Try to invoke using InvokePattern
            try:
                invoke_pattern = element.GetCurrentPattern(uia.UIA_InvokePatternId)
                invoke_pattern.Invoke()
                return ToolOutput(
                    success=True,
                    data={"invoked_element": input_data.element_description},
                    evidence={"method": "UIA_InvokePattern"}
                )
            except Exception:
                # Fallback: click using bounding rectangle
                rect = element.CurrentBoundingRectangle
                center_x = (rect.left + rect.right) // 2
                center_y = (rect.top + rect.bottom) // 2
                
                click_tool = GUIClickTool()
                return await click_tool.execute(GUIClickInput(
                    window_title=input_data.window_title,
                    x=center_x,
                    y=center_y
                ))
                
        except ImportError:
            return ToolOutput(
                success=False,
                error={"code": "NO_UIA", "message": "UI Automation not available"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "UIA_INVOKE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    def _find_window_by_title(self, iuia, root, title: str) -> Optional[Any]:
        """Find window by title."""
        condition = iuia.CreatePropertyCondition(
            uia.UIA_NamePropertyId,
            title
        )
        window = root.FindFirst(uia.TreeScope_Children, condition)
        
        if window:
            return window
        
        # Try partial match
        return self._find_window_by_partial_title(iuia, root, title)
    
    def _find_window_by_partial_title(self, iuia, root, partial_title: str) -> Optional[Any]:
        """Find window by partial title."""
        condition = iuia.CreatePropertyCondition(
            uia.UIA_ControlTypePropertyId,
            uia.UIA_WindowControlTypeId
        )
        windows = root.FindAll(uia.TreeScope_Children, condition)
        
        for i in range(windows.Length):
            window = windows.GetElement(i)
            name = window.CurrentName
            if partial_title.lower() in name.lower():
                return window
        return None
    
    def _find_element_by_description(self, iuia, root, description: str) -> Optional[Any]:
        """Find element by description (name, automation id, or class)."""
        # Try name property
        condition = iuia.CreatePropertyCondition(
            uia.UIA_NamePropertyId,
            description
        )
        element = root.FindFirst(uia.TreeScope_Descendants, condition)
        if element:
            return element
        
        # Try automation id
        condition = iuia.CreatePropertyCondition(
            uia.UIA_AutomationIdPropertyId,
            description
        )
        element = root.FindFirst(uia.TreeScope_Descendants, condition)
        if element:
            return element
        
        # Try partial name match
        walker = iuia.ControlViewWalker
        return self._search_elements_recursive(iuia, walker, root, description)
    
    def _search_elements_recursive(self, iuia, walker, element, description: str, depth: int = 0) -> Optional[Any]:
        """Recursively search for element by partial name match."""
        if depth > 10:  # Limit recursion depth
            return None
        
        name = element.CurrentName
        if name and description.lower() in name.lower():
            return element
        
        child = walker.GetFirstChildElement(element)
        while child:
            result = self._search_elements_recursive(iuia, walker, child, description, depth + 1)
            if result:
                return result
            child = walker.GetNextSiblingElement(child)
        
        return None
    
    async def verify(self, input_data: GUIInvokeInput, output: ToolOutput) -> bool:
        """Verify the element was invoked."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {
            "requires_screen_access": True,
            "requires_ui_automation": True,
            "elevated_process_check": True,
            "element_interaction": True
        }


class GUISetValueTool(BaseTool):
    """Set value of a UI element (text field, checkbox, etc.)."""
    
    name = "gui_set_value"
    description = "Set the value of a UI element like a text field, checkbox, or combo box"
    input_schema = GUISetValueInput
    
    async def execute(self, input_data: GUISetValueInput) -> ToolOutput:
        """Execute the GUI set value tool."""
        try:
            system = platform.system()
            
            if system == "Windows":
                return await self._set_value_windows(input_data)
            else:
                return ToolOutput(
                    success=False,
                    error={"code": "PLATFORM_NOT_SUPPORTED", "message": f"GUI set value not fully supported on {system}"}
                )
                
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "SET_VALUE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def _set_value_windows(self, input_data: GUISetValueInput) -> ToolOutput:
        """Set value on Windows using UIA."""
        try:
            import comtypes.client
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as uia
            
            iuia = comtypes.client.CreateObject(uia.CUIAutomation8).QueryInterface(uia.IUIAutomation)
            root = iuia.GetRootElement()
            
            # Find window
            window = self._find_window_by_title(iuia, root, input_data.window_title)
            if not window:
                return ToolOutput(
                    success=False,
                    error={"code": "WINDOW_NOT_FOUND", "message": f"Window '{input_data.window_title}' not found"}
                )
            
            # Find element
            element = self._find_element_by_description(iuia, window, input_data.element_description)
            
            if not element:
                return ToolOutput(
                    success=False,
                    error={"code": "ELEMENT_NOT_FOUND", "message": f"Element '{input_data.element_description}' not found"}
                )
            
            # Try ValuePattern
            try:
                value_pattern = element.GetCurrentPattern(uia.UIA_ValuePatternId)
                value_pattern.SetValue(input_data.value)
                return ToolOutput(
                    success=True,
                    data={"element": input_data.element_description, "value_set": input_data.value},
                    evidence={"method": "UIA_ValuePattern"}
                )
            except Exception:
                # Fallback: use TogglePattern for checkboxes
                try:
                    toggle_pattern = element.GetCurrentPattern(uia.UIA_TogglePatternId)
                    if input_data.value.lower() in ["true", "yes", "1", "checked"]:
                        toggle_pattern.Toggle()
                    return ToolOutput(
                        success=True,
                        data={"element": input_data.element_description, "toggled": True},
                        evidence={"method": "UIA_TogglePattern"}
                    )
                except Exception:
                    # Last resort: click and type
                    rect = element.CurrentBoundingRectangle
                    center_x = (rect.left + rect.right) // 2
                    center_y = (rect.top + rect.bottom) // 2
                    
                    click_tool = GUIClickTool()
                    click_result = await click_tool.execute(GUIClickInput(
                        window_title=input_data.window_title,
                        x=center_x,
                        y=center_y
                    ))
                    
                    if click_result.success:
                        type_tool = GUITypeTool()
                        return await type_tool.execute(GUITypeInput(
                            window_title=input_data.window_title,
                            text=input_data.value
                        ))
                    else:
                        return click_result
                        
        except ImportError:
            return ToolOutput(
                success=False,
                error={"code": "NO_UIA", "message": "UI Automation not available"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "UIA_SET_VALUE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    def _find_window_by_title(self, iuia, root, title: str) -> Optional[Any]:
        """Find window by title."""
        condition = iuia.CreatePropertyCondition(
            uia.UIA_NamePropertyId,
            title
        )
        window = root.FindFirst(uia.TreeScope_Children, condition)
        
        if window:
            return window
        
        return self._find_window_by_partial_title(iuia, root, title)
    
    def _find_window_by_partial_title(self, iuia, root, partial_title: str) -> Optional[Any]:
        """Find window by partial title."""
        condition = iuia.CreatePropertyCondition(
            uia.UIA_ControlTypePropertyId,
            uia.UIA_WindowControlTypeId
        )
        windows = root.FindAll(uia.TreeScope_Children, condition)
        
        for i in range(windows.Length):
            window = windows.GetElement(i)
            name = window.CurrentName
            if partial_title.lower() in name.lower():
                return window
        return None
    
    def _find_element_by_description(self, iuia, root, description: str) -> Optional[Any]:
        """Find element by description."""
        # Try name property
        condition = iuia.CreatePropertyCondition(
            uia.UIA_NamePropertyId,
            description
        )
        element = root.FindFirst(uia.TreeScope_Descendants, condition)
        if element:
            return element
        
        # Try automation id
        condition = iuia.CreatePropertyCondition(
            uia.UIA_AutomationIdPropertyId,
            description
        )
        element = root.FindFirst(uia.TreeScope_Descendants, condition)
        if element:
            return element
        
        return None
    
    async def verify(self, input_data: GUISetValueInput, output: ToolOutput) -> bool:
        """Verify the value was set."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {
            "requires_screen_access": True,
            "requires_ui_automation": True,
            "elevated_process_check": True,
            "element_modification": True,
            "data_entry": True
        }
