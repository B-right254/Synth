"""
Package Management Tools for JARVIS
Implements package operations: search, list, install, uninstall
Platform-specific implementations for Windows (winget/chocolatey), macOS (brew), Linux (apt/dnf/pacman)
"""
import subprocess
import platform
import json
from typing import Dict, Any, List, Optional

from tools.executor import BaseTool
from api.schemas import (
    ToolOutput,
    PackageSearchInput,
    PackageListInput,
    PackageInstallInput,
    PackageUninstallInput,
)


class PackageSearchTool(BaseTool):
    """Search for packages in package managers."""
    
    name = "package_search"
    description = "Search for packages in system package managers"
    input_schema = PackageSearchInput
    
    async def execute(self, input_data: PackageSearchInput) -> ToolOutput:
        """Execute the package search tool."""
        try:
            system = platform.system()
            results = []
            
            if system == "Windows":
                # Try winget first
                try:
                    result = subprocess.run(
                        ["winget", "search", input_data.query, "--format", "json"],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0:
                        try:
                            data = json.loads(result.stdout)
                            for pkg in data.get('Packages', [])[:input_data.limit]:
                                results.append({
                                    "id": pkg.get('Id', ''),
                                    "name": pkg.get('Name', ''),
                                    "version": pkg.get('Version', ''),
                                    "source": pkg.get('Source', 'winget'),
                                    "platform": "windows"
                                })
                        except json.JSONDecodeError:
                            pass
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                
                # Try chocolatey if winget not available
                if not results:
                    try:
                        result = subprocess.run(
                            ["choco", "search", input_data.query, "-r"],
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if result.returncode == 0:
                            for line in result.stdout.strip().split('\n')[:input_data.limit]:
                                if '|' in line:
                                    parts = line.split('|')
                                    results.append({
                                        "id": parts[0],
                                        "name": parts[1] if len(parts) > 1 else parts[0],
                                        "version": parts[2] if len(parts) > 2 else None,
                                        "source": "chocolatey",
                                        "platform": "windows"
                                    })
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        pass
            
            elif system == "Darwin":
                # Homebrew search
                try:
                    result = subprocess.run(
                        ["brew", "search", "--json=v2", input_data.query],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        for formula in data.get('formulae', [])[:input_data.limit]:
                            results.append({
                                "id": formula.get('name', ''),
                                "name": formula.get('name', ''),
                                "version": formula.get('versions', {}).get('stable', None),
                                "source": "homebrew",
                                "platform": "macos"
                            })
                        for cask in data.get('casks', [])[:input_data.limit - len(results)]:
                            results.append({
                                "id": cask.get('token', ''),
                                "name": cask.get('name', [cask.get('token', '')])[0] if isinstance(cask.get('name'), list) else cask.get('name', ''),
                                "version": cask.get('version', None),
                                "source": "homebrew-cask",
                                "platform": "macos"
                            })
                except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
                    pass
            
            else:
                # Linux: Try multiple package managers
                package_managers = [
                    ("apt", ["apt-cache", "search", input_data.query]),
                    ("dnf", ["dnf", "search", "-q", input_data.query]),
                    ("pacman", ["pacman", "-Ss", input_data.query]),
                    ("snap", ["snap", "find", input_data.query]),
                ]
                
                for pm_name, cmd in package_managers:
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            count = 0
                            for line in lines:
                                if count >= input_data.limit:
                                    break
                                if pm_name == "apt" and '/' in line:
                                    parts = line.split('/')
                                    pkg_id = parts[0].strip()
                                    desc = parts[1].strip() if len(parts) > 1 else ''
                                    results.append({
                                        "id": pkg_id,
                                        "name": pkg_id,
                                        "description": desc,
                                        "source": "apt",
                                        "platform": "linux"
                                    })
                                    count += 1
                                elif pm_name == "dnf" and '.' in line:
                                    parts = line.split('.')
                                    pkg_id = parts[0].strip()
                                    results.append({
                                        "id": pkg_id,
                                        "name": pkg_id,
                                        "source": "dnf",
                                        "platform": "linux"
                                    })
                                    count += 1
                            break  # Use first successful package manager
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
            
            return ToolOutput(
                success=True,
                data={
                    "query": input_data.query,
                    "count": len(results),
                    "limit": input_data.limit,
                    "packages": results,
                    "platform": system
                },
                evidence={"source": "package_manager_search"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "PACKAGE_SEARCH_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: PackageSearchInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "packages" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "none", "requires_confirmation": False}


class PackageListTool(BaseTool):
    """List installed packages."""
    
    name = "package_list"
    description = "List installed packages on the system"
    input_schema = PackageListInput
    
    async def execute(self, input_data: PackageListInput) -> ToolOutput:
        """Execute the package list tool."""
        try:
            system = platform.system()
            packages = []
            
            if system == "Windows":
                # winget list
                try:
                    result = subprocess.run(
                        ["winget", "list", "--format", "json"],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        try:
                            data = json.loads(result.stdout)
                            for pkg in data:
                                name = pkg.get('Name', '')
                                if input_data.search_term and input_data.search_term.lower() not in name.lower():
                                    continue
                                packages.append({
                                    "id": pkg.get('Id', ''),
                                    "name": name,
                                    "version": pkg.get('Version', ''),
                                    "source": "winget",
                                    "platform": "windows"
                                })
                        except json.JSONDecodeError:
                            pass
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            
            elif system == "Darwin":
                # brew list
                try:
                    result = subprocess.run(
                        ["brew", "list", "--formula", "--json=v2"],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        for formula in data.get('formulae', []):
                            name = formula.get('name', '')
                            if input_data.search_term and input_data.search_term.lower() not in name.lower():
                                continue
                            packages.append({
                                "id": name,
                                "name": name,
                                "version": formula.get('versions', {}).get('installed', [''])[0] if formula.get('versions', {}).get('installed') else '',
                                "source": "homebrew",
                                "platform": "macos"
                            })
                except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
                    pass
            
            else:
                # Linux: apt list --installed
                try:
                    result = subprocess.run(
                        ["apt", "list", "--installed"],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                            if '/' in line:
                                parts = line.split('/')
                                pkg_id = parts[0].strip()
                                if input_data.search_term and input_data.search_term.lower() not in pkg_id.lower():
                                    continue
                                version_part = parts[1].strip() if len(parts) > 1 else ''
                                packages.append({
                                    "id": pkg_id,
                                    "name": pkg_id,
                                    "version": version_part.split()[0] if version_part else '',
                                    "source": "apt",
                                    "platform": "linux"
                                })
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            
            return ToolOutput(
                success=True,
                data={
                    "count": len(packages),
                    "search_term": input_data.search_term,
                    "packages": packages[:200],  # Limit output
                    "platform": system
                },
                evidence={"source": "package_manager_list"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "PACKAGE_LIST_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: PackageListInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success and "packages" in (output.data or {})
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "none", "requires_confirmation": False}


class PackageInstallTool(BaseTool):
    """Install a package."""
    
    name = "package_install"
    description = "Install a package using system package manager"
    input_schema = PackageInstallInput
    
    async def execute(self, input_data: PackageInstallInput) -> ToolOutput:
        """Execute the package install tool."""
        try:
            system = platform.system()
            package_id = input_data.package_id
            source = input_data.source
            
            if system == "Windows":
                # Determine package manager
                if source == "chocolatey" or not source:
                    try:
                        result = subprocess.run(
                            ["choco", "install", package_id, "-y"],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        method = "chocolatey"
                        success = result.returncode == 0
                    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                        return ToolOutput(
                            success=False,
                            error={"code": "INSTALL_ERROR", "message": f"Chocolatey not available: {str(e)}"},
                            duration_ms=0
                        )
                else:
                    try:
                        result = subprocess.run(
                            ["winget", "install", "--id", package_id, "--silent", "--accept-package-agreements", "--accept-source-agreements"],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        method = "winget"
                        success = result.returncode == 0
                    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                        return ToolOutput(
                            success=False,
                            error={"code": "INSTALL_ERROR", "message": f"Winget not available: {str(e)}"},
                            duration_ms=0
                        )
            
            elif system == "Darwin":
                try:
                    result = subprocess.run(
                        ["brew", "install", package_id],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    method = "homebrew"
                    success = result.returncode == 0
                except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                    return ToolOutput(
                        success=False,
                        error={"code": "INSTALL_ERROR", "message": f"Homebrew not available: {str(e)}"},
                        duration_ms=0
                    )
            
            else:
                # Linux: Try apt with sudo
                try:
                    result = subprocess.run(
                        ["sudo", "apt", "install", "-y", package_id],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    method = "apt"
                    success = result.returncode == 0
                except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                    return ToolOutput(
                        success=False,
                        error={"code": "INSTALL_ERROR", "message": f"Package installation failed: {str(e)}"},
                        duration_ms=0
                    )
            
            return ToolOutput(
                success=success,
                data={
                    "package_id": package_id,
                    "method": method,
                    "platform": system,
                    "source": source
                } if success else None,
                error=None if success else {"code": "INSTALL_FAILED", "message": f"Failed to install {package_id}"},
                evidence={"source": "package_manager_install"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "INSTALL_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: PackageInstallInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "high", "requires_confirmation": True, "requires_admin": True}


class PackageUninstallTool(BaseTool):
    """Uninstall a package."""
    
    name = "package_uninstall"
    description = "Uninstall a package from the system"
    input_schema = PackageUninstallInput
    
    async def execute(self, input_data: PackageUninstallInput) -> ToolOutput:
        """Execute the package uninstall tool."""
        try:
            system = platform.system()
            package_id = input_data.package_id
            
            if system == "Windows":
                # Try winget first
                try:
                    result = subprocess.run(
                        ["winget", "uninstall", "--id", package_id, "--silent", "--purge"],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    method = "winget"
                    success = result.returncode == 0
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    # Fallback to choco
                    try:
                        result = subprocess.run(
                            ["choco", "uninstall", package_id, "-y"],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        method = "chocolatey"
                        success = result.returncode == 0
                    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                        return ToolOutput(
                            success=False,
                            error={"code": "UNINSTALL_ERROR", "message": "No package manager available"},
                            duration_ms=0
                        )
            
            elif system == "Darwin":
                try:
                    result = subprocess.run(
                        ["brew", "uninstall", package_id],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    method = "homebrew"
                    success = result.returncode == 0
                except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                    return ToolOutput(
                        success=False,
                        error={"code": "UNINSTALL_ERROR", "message": f"Homebrew not available: {str(e)}"},
                        duration_ms=0
                    )
            
            else:
                # Linux: apt remove
                try:
                    result = subprocess.run(
                        ["sudo", "apt", "remove", "-y", package_id],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    method = "apt"
                    success = result.returncode == 0
                except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                    return ToolOutput(
                        success=False,
                        error={"code": "UNINSTALL_ERROR", "message": f"Uninstallation failed: {str(e)}"},
                        duration_ms=0
                    )
            
            return ToolOutput(
                success=success,
                data={
                    "package_id": package_id,
                    "method": method,
                    "platform": system
                } if success else None,
                error=None if success else {"code": "UNINSTALL_FAILED", "message": f"Failed to uninstall {package_id}"},
                evidence={"source": "package_manager_uninstall"}
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error={"code": "UNINSTALL_ERROR", "message": str(e)},
                duration_ms=0
            )
    
    async def verify(self, input_data: PackageUninstallInput, output: ToolOutput) -> bool:
        """Verify the tool execution result."""
        return output.success
    
    def get_policy_requirements(self) -> Dict[str, Any]:
        """Get policy requirements for this tool."""
        return {"risk_level": "high", "requires_confirmation": True, "destructive": True, "requires_admin": True}


def create_package_tools() -> List[BaseTool]:
    """Create instances of all package tools."""
    return [
        PackageSearchTool(),
        PackageListTool(),
        PackageInstallTool(),
        PackageUninstallTool(),
    ]
