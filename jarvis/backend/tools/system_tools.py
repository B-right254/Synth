"""
System read tools for JARVIS.
Direct OS APIs for reading system state.
"""

import platform
import psutil
from datetime import datetime
from typing import Dict, Any, Optional

# Use absolute import instead of relative
try:
    from tools.executor import BaseTool
    from api.schemas import (
        ToolOutput,
        SystemTimeInput,
        SystemBatteryInput,
        SystemDiskInput,
        SystemProcessesInput,
        SystemActiveWindowInput,
    )
except ImportError:
    try:
        from jarvis_backend.tools.executor import BaseTool
        from jarvis_backend.api.schemas import (
            ToolOutput,
            SystemTimeInput,
            SystemBatteryInput,
            SystemDiskInput,
            SystemProcessesInput,
            SystemActiveWindowInput,
        )
    except ImportError:
        # Minimal fallbacks
        class BaseTool:
            pass
        
        class ToolOutput:
            pass
        
        class SystemTimeInput:
            pass
        
        class SystemBatteryInput:
            pass
        
        class SystemDiskInput:
            pass
        
        class SystemProcessesInput:
            pass
        
        class SystemActiveWindowInput:
            pass


class SystemTimeTool(BaseTool):
    """Get current system time and date."""
    
    name = "system_time"
    description = "Get the current system time and date"
    input_schema = SystemTimeInput
    
    async def execute(self, input_data: SystemTimeInput) -> ToolOutput:
        now = datetime.now()
        return ToolOutput(
            success=True,
            data={
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": datetime.now().astimezone().tzname(),
            },
            evidence={"source": "system_clock"}
        )
    
    async def verify(self, input_data: SystemTimeInput, output: ToolOutput) -> bool:
        return output.success and "datetime" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        return {"risk_level": "none", "requires_confirmation": False}


class SystemBatteryTool(BaseTool):
    """Get battery status information."""
    
    name = "system_battery"
    description = "Get battery status and charge level"
    input_schema = SystemBatteryInput
    
    async def execute(self, input_data: SystemBatteryInput) -> ToolOutput:
        """Execute the battery status tool."""
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return ToolOutput(
                    success=True,
                    data={"available": False, "message": "No battery detected"},
                    evidence={"source": "psutil"}
                )
            
            return ToolOutput(
                success=True,
                data={
                    "available": True,
                    "percent": battery.percent,
                    "plugged_in": battery.power_plugged,
                    "time_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
                },
                evidence={"source": "psutil_sensors"}
            )
        except Exception as e:
            # Return success with no battery info instead of failure for environments without battery sensors
            return ToolOutput(
                success=True,
                data={"available": False, "message": f"Battery sensor not available: {str(e)}"},
                evidence={"source": "psutil_error"}
            )
    
    async def verify(self, input_data: SystemBatteryInput, output: ToolOutput) -> bool:
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        return {"risk_level": "none", "requires_confirmation": False}


class SystemDiskTool(BaseTool):
    """Get disk space information."""
    
    name = "system_disk"
    description = "Get disk space usage information"
    input_schema = SystemDiskInput
    
    async def execute(self, input_data: SystemDiskInput) -> ToolOutput:
        try:
            path = input_data.path or "/"
            usage = psutil.disk_usage(path)
            
            return ToolOutput(
                success=True,
                data={
                    "path": path,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent_used": usage.percent,
                },
                evidence={"source": "psutil_disk", "path": path}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "DISK_READ_ERROR", "message": str(e)}
            )
    
    async def verify(self, input_data: SystemDiskInput, output: ToolOutput) -> bool:
        return output.success and "total_gb" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        return {"risk_level": "none", "requires_confirmation": False}


class SystemProcessesTool(BaseTool):
    """Get list of running processes (redacted)."""
    
    name = "system_processes"
    description = "Get list of running processes (limited, redacted)"
    input_schema = SystemProcessesInput
    
    async def execute(self, input_data: SystemProcessesInput) -> ToolOutput:
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by name and limit
            processes.sort(key=lambda x: x['name'].lower())
            processes = processes[:input_data.limit]
            
            return ToolOutput(
                success=True,
                data={
                    "count": len(processes),
                    "limit": input_data.limit,
                    "processes": processes,
                },
                evidence={"source": "psutil_processes"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "PROCESS_LIST_ERROR", "message": str(e)}
            )
    
    async def verify(self, input_data: SystemProcessesInput, output: ToolOutput) -> bool:
        return output.success and "processes" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        return {"risk_level": "low", "requires_confirmation": False, "redact_sensitive": True}


class SystemActiveWindowTool(BaseTool):
    """Get active window information."""
    
    name = "system_active_window"
    description = "Get information about the currently active window"
    input_schema = SystemActiveWindowInput
    
    async def execute(self, input_data: SystemActiveWindowInput) -> ToolOutput:
        try:
            # Note: Full implementation requires Windows-specific APIs
            # This is a placeholder that will be enhanced with win32gui on Windows
            try:
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                
                return ToolOutput(
                    success=True,
                    data={
                        "hwnd": hwnd,
                        "title": title,
                        "is_visible": win32gui.IsWindowVisible(hwnd),
                    },
                    evidence={"source": "win32gui"}
                )
            except ImportError:
                # Fallback for non-Windows (development/testing)
                return ToolOutput(
                    success=True,
                    data={
                        "hwnd": None,
                        "title": "N/A (not on Windows)",
                        "platform": platform.system(),
                    },
                    evidence={"source": "platform_fallback"}
                )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "WINDOW_READ_ERROR", "message": str(e)}
            )
    
    async def verify(self, input_data: SystemActiveWindowInput, output: ToolOutput) -> bool:
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        return {"risk_level": "none", "requires_confirmation": False}


# Register all system tools
def create_system_tools() -> list:
    """Create instances of all system read tools."""
    return [
        SystemTimeTool(),
        SystemBatteryTool(),
        SystemDiskTool(),
        SystemProcessesTool(),
        SystemActiveWindowTool(),
    ]
