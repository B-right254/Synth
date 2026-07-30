"""
File System Tools for JARVIS
Implements file operations: read, write, list, create, delete, move, copy
"""
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

from backend.tools.executor import BaseTool
from backend.api.schemas import (
    ToolOutput,
    FileListInput,
    FileReadInput,
    FileCreateInput,
    FileWriteInput,
    FileMoveInput,
    FileCopyInput,
    FileDeleteInput,
)


class FileListTool(BaseTool):
    """List directory contents."""
    
    name = "file_list"
    description = "List files and directories in a given path"
    input_schema = FileListInput
    
    async def execute(self, input_data: FileListInput) -> ToolOutput:
        """Execute the file list tool."""
        try:
            path = Path(input_data.path).expanduser().resolve()
            
            if not path.exists():
                return ToolOutput(
                    success=False,
                    error={"code": "PATH_NOT_FOUND", "message": f"Path not found: {path}"},
                    duration_ms=0
                )
            
            if not path.is_dir():
                return ToolOutput(
                    success=False,
                    error={"code": "NOT_DIRECTORY", "message": f"Path is not a directory: {path}"},
                    duration_ms=0
                )
            
            items = []
            for item in path.iterdir():
                # Skip hidden files unless requested
                if not input_data.include_hidden and item.name.startswith('.'):
                    continue
                
                try:
                    stat_info = item.stat()
                    items.append({
                        "name": item.name,
                        "path": str(item),
                        "is_file": item.is_file(),
                        "is_dir": item.is_dir(),
                        "size": stat_info.st_size if item.is_file() else None,
                        "modified": stat_info.st_mtime
                    })
                except (PermissionError, OSError):
                    items.append({
                        "name": item.name,
                        "path": str(item),
                        "error": "Permission denied"
                    })
            
            # Sort: directories first, then files
            items.sort(key=lambda x: (not x.get('is_dir', False), x['name'].lower()))
            
            return ToolOutput(
                success=True,
                data={
                    "path": str(path),
                    "count": len(items),
                    "items": items
                },
                evidence={"source": "filesystem_list"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "LIST_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: FileListInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "items" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "none", "requires_confirmation": False}


class FileReadTool(BaseTool):
    """Read file contents."""
    
    name = "file_read"
    description = "Read the contents of a file"
    input_schema = FileReadInput
    
    async def execute(self, input_data: FileReadInput) -> ToolOutput:
        """Execute the file read tool."""
        try:
            path = Path(input_data.path).expanduser().resolve()
            
            if not path.exists():
                return ToolOutput(
                    success=False,
                    error={"code": "FILE_NOT_FOUND", "message": f"File not found: {path}"},
                    duration_ms=0
                )
            
            if not path.is_file():
                return ToolOutput(
                    success=False,
                    error={"code": "NOT_FILE", "message": f"Path is not a file: {path}"},
                    duration_ms=0
                )
            
            # Check file size before reading
            file_size = path.stat().st_size
            if file_size > input_data.max_bytes:
                return ToolOutput(
                    success=False,
                    error={
                        "code": "FILE_TOO_LARGE",
                        "message": f"File size ({file_size} bytes) exceeds maximum allowed ({input_data.max_bytes} bytes)"
                    },
                    duration_ms=0
                )
            
            content = path.read_text(encoding='utf-8', errors='replace')
            
            return ToolOutput(
                success=True,
                data={
                    "path": str(path),
                    "content": content,
                    "size": len(content),
                    "bytes_read": file_size
                },
                evidence={"source": "filesystem_read"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "READ_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: FileReadInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "content" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "low", "requires_confirmation": False, "redact_sensitive": True}


class FileCreateTool(BaseTool):
    """Create a new file."""
    
    name = "file_create"
    description = "Create a new file with specified content"
    input_schema = FileCreateInput
    
    async def execute(self, input_data: FileCreateInput) -> ToolOutput:
        """Execute the file create tool."""
        try:
            path = Path(input_data.path).expanduser().resolve()
            
            # Check if file already exists
            if path.exists():
                if not input_data.overwrite:
                    return ToolOutput(
                        success=False,
                        error={"code": "FILE_EXISTS", "message": f"File already exists: {path}. Use overwrite=True to replace."},
                        duration_ms=0
                    )
                # If overwrite is True, we'll proceed to write
            
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            path.write_text(input_data.content, encoding='utf-8')
            
            return ToolOutput(
                success=True,
                data={
                    "path": str(path),
                    "bytes_written": len(input_data.content.encode('utf-8')),
                    "overwritten": path.exists() and input_data.overwrite
                },
                evidence={"source": "filesystem_create"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "CREATE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: FileCreateInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "path" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "medium", "requires_confirmation": True, "confirm_overwrite": True}


class FileWriteTool(BaseTool):
    """Write content to a file."""
    
    name = "file_write"
    description = "Write or append content to a file"
    input_schema = FileWriteInput
    
    async def execute(self, input_data: FileWriteInput) -> ToolOutput:
        """Execute the file write tool."""
        try:
            path = Path(input_data.path).expanduser().resolve()
            
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if input_data.append else 'w'
            with open(path, mode, encoding='utf-8') as f:
                f.write(input_data.content)
            
            return ToolOutput(
                success=True,
                data={
                    "path": str(path),
                    "bytes_written": len(input_data.content.encode('utf-8')),
                    "appended": input_data.append
                },
                evidence={"source": "filesystem_write"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "WRITE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: FileWriteInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "path" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "medium", "requires_confirmation": True}


class FileMoveTool(BaseTool):
    """Move a file to a new location."""
    
    name = "file_move"
    description = "Move a file from source to destination"
    input_schema = FileMoveInput
    
    async def execute(self, input_data: FileMoveInput) -> ToolOutput:
        """Execute the file move tool."""
        try:
            source = Path(input_data.source_path).expanduser().resolve()
            dest = Path(input_data.destination_path).expanduser().resolve()
            
            if not source.exists():
                return ToolOutput(
                    success=False,
                    error={"code": "SOURCE_NOT_FOUND", "message": f"Source file not found: {source}"},
                    duration_ms=0
                )
            
            if not source.is_file():
                return ToolOutput(
                    success=False,
                    error={"code": "SOURCE_NOT_FILE", "message": f"Source is not a file: {source}"},
                    duration_ms=0
                )
            
            # Check if destination exists
            if dest.exists() and not input_data.overwrite:
                return ToolOutput(
                    success=False,
                    error={"code": "DESTINATION_EXISTS", "message": f"Destination already exists: {dest}. Use overwrite=True to replace."},
                    duration_ms=0
                )
            
            # Create parent directories if needed
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the file
            shutil.move(str(source), str(dest))
            
            return ToolOutput(
                success=True,
                data={
                    "source": str(source),
                    "destination": str(dest),
                    "overwritten": dest.exists() and input_data.overwrite
                },
                evidence={"source": "filesystem_move"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "MOVE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: FileMoveInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "destination" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "medium", "requires_confirmation": True}


class FileCopyTool(BaseTool):
    """Copy a file to a new location."""
    
    name = "file_copy"
    description = "Copy a file from source to destination"
    input_schema = FileCopyInput
    
    async def execute(self, input_data: FileCopyInput) -> ToolOutput:
        """Execute the file copy tool."""
        try:
            source = Path(input_data.source_path).expanduser().resolve()
            dest = Path(input_data.destination_path).expanduser().resolve()
            
            if not source.exists():
                return ToolOutput(
                    success=False,
                    error={"code": "SOURCE_NOT_FOUND", "message": f"Source file not found: {source}"},
                    duration_ms=0
                )
            
            if not source.is_file():
                return ToolOutput(
                    success=False,
                    error={"code": "SOURCE_NOT_FILE", "message": f"Source is not a file: {source}"},
                    duration_ms=0
                )
            
            # Check if destination exists
            if dest.exists() and not input_data.overwrite:
                return ToolOutput(
                    success=False,
                    error={"code": "DESTINATION_EXISTS", "message": f"Destination already exists: {dest}. Use overwrite=True to replace."},
                    duration_ms=0
                )
            
            # Create parent directories if needed
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the file
            shutil.copy2(str(source), str(dest))
            
            return ToolOutput(
                success=True,
                data={
                    "source": str(source),
                    "destination": str(dest),
                    "overwritten": dest.exists() and input_data.overwrite
                },
                evidence={"source": "filesystem_copy"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "COPY_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: FileCopyInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "destination" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "medium", "requires_confirmation": True}


class FileDeleteTool(BaseTool):
    """Delete a file."""
    
    name = "file_delete"
    description = "Delete a file (optionally using recycle bin)"
    input_schema = FileDeleteInput
    
    async def execute(self, input_data: FileDeleteInput) -> ToolOutput:
        """Execute the file delete tool."""
        try:
            path = Path(input_data.path).expanduser().resolve()
            
            if not path.exists():
                return ToolOutput(
                    success=False,
                    error={"code": "FILE_NOT_FOUND", "message": f"File not found: {path}"},
                    duration_ms=0
                )
            
            if not path.is_file():
                return ToolOutput(
                    success=False,
                    error={"code": "NOT_FILE", "message": f"Path is not a file: {path}"},
                    duration_ms=0
                )
            
            # On Windows, use recycle bin if requested
            if input_data.use_recycle_bin:
                try:
                    import send2trash
                    send2trash.send2trash(str(path))
                    method = "recycle_bin"
                except ImportError:
                    # Fallback to permanent deletion if send2trash not available
                    path.unlink()
                    method = "permanent_deletion_no_send2trash"
            else:
                path.unlink()
                method = "permanent_deletion"
            
            return ToolOutput(
                success=True,
                data={
                    "path": str(path),
                    "deletion_method": method
                },
                evidence={"source": "filesystem_delete"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "DELETE_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: FileDeleteInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "path" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "high", "requires_confirmation": True, "destructive": True}


def create_file_tools() -> List[BaseTool]:
    """Create instances of all file tools."""
    return [
        FileListTool(),
        FileReadTool(),
        FileCreateTool(),
        FileWriteTool(),
        FileMoveTool(),
        FileCopyTool(),
        FileDeleteTool(),
    ]
