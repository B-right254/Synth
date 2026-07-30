"""
Skills System for JARVIS
Manages skill definitions, registration, and execution.
Skills are composable units of functionality that can be invoked by the LLM.
"""
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)

class SkillCategory(str, Enum):
    """Categories of skills."""
    SYSTEM = "system"
    FILE = "file"
    APPLICATION = "application"
    PACKAGE = "package"
    COMMUNICATION = "communication"
    BROWSER = "browser"
    MEDIA = "media"
    CUSTOM = "custom"

class SkillParameter(BaseModel):
    """Definition of a skill parameter."""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None

class SkillDefinition(BaseModel):
    """Definition of a skill."""
    id: str
    name: str
    description: str
    category: SkillCategory
    parameters: List[SkillParameter] = []
    returns: str = "string"
    examples: List[str] = []
    risk_level: str = "low"  # "low", "medium", "high", "critical"
    requires_confirmation: bool = False

class SkillResult(BaseModel):
    """Result of skill execution."""
    success: bool
    output: Any
    error: Optional[str] = None
    evidence: Optional[str] = None
    duration_ms: Optional[int] = None

class Skill:
    """Executable skill wrapper."""
    
    def __init__(self, definition: SkillDefinition, handler: Callable[..., Awaitable[SkillResult]]):
        self.definition = definition
        self.handler = handler
        
    async def execute(self, **kwargs) -> SkillResult:
        """Execute the skill with provided parameters."""
        import time
        start = time.time()
        
        try:
            # Validate parameters
            self._validate_params(kwargs)
            
            # Execute handler
            result = await self.handler(**kwargs)
            result.duration_ms = int((time.time() - start) * 1000)
            return result
            
        except Exception as e:
            logger.error(f"Skill {self.definition.id} execution failed: {e}")
            return SkillResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=int((time.time() - start) * 1000)
            )
            
    def _validate_params(self, params: Dict[str, Any]):
        """Validate provided parameters against definition."""
        for param in self.definition.parameters:
            if param.required and param.name not in params:
                raise ValueError(f"Missing required parameter: {param.name}")
                
        # Type checking could be added here

class SkillsRegistry:
    """Central registry for all skills."""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._categories: Dict[SkillCategory, List[str]] = {cat: [] for cat in SkillCategory}
        
    def register(self, skill: Skill):
        """Register a skill."""
        self._skills[skill.definition.id] = skill
        self._categories[skill.definition.category].append(skill.definition.id)
        logger.info(f"Registered skill: {skill.definition.id} ({skill.definition.name})")
        
    def unregister(self, skill_id: str):
        """Unregister a skill."""
        if skill_id in self._skills:
            skill = self._skills[skill_id]
            self._categories[skill.definition.category].remove(skill_id)
            del self._skills[skill_id]
            logger.info(f"Unregistered skill: {skill_id}")
            
    def get(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)
        
    def list_skills(self, category: Optional[SkillCategory] = None) -> List[SkillDefinition]:
        """List all registered skills, optionally filtered by category."""
        if category:
            skill_ids = self._categories.get(category, [])
            return [self._skills[sid].definition for sid in skill_ids if sid in self._skills]
        return [skill.definition for skill in self._skills.values()]
        
    def search_skills(self, query: str) -> List[SkillDefinition]:
        """Search skills by name or description."""
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if (query_lower in skill.definition.name.lower() or 
                query_lower in skill.definition.description.lower()):
                results.append(skill.definition)
        return results
        
    def get_skill_prompt(self, skill_id: str) -> str:
        """Generate a prompt description for a skill (for LLM context)."""
        skill = self._skills.get(skill_id)
        if not skill:
            return ""
            
        d = skill.definition
        prompt = f"## {d.name} ({d.id})\n"
        prompt += f"**Description**: {d.description}\n"
        prompt += f"**Category**: {d.category.value}\n"
        prompt += f"**Risk Level**: {d.risk_level}\n"
        
        if d.parameters:
            prompt += "**Parameters**:\n"
            for param in d.parameters:
                req = "required" if param.required else "optional"
                prompt += f"  - `{param.name}` ({param.type}, {req}): {param.description}\n"
                if param.default is not None:
                    prompt += f"    Default: {param.default}\n"
                    
        if d.examples:
            prompt += "**Examples**:\n"
            for ex in d.examples:
                prompt += f"  - {ex}\n"
                
        return prompt
        
    def get_all_prompts(self) -> str:
        """Generate prompts for all skills (for system prompt construction)."""
        prompts = []
        for skill in self._skills.values():
            prompts.append(self.get_skill_prompt(skill.definition.id))
        return "\n\n".join(prompts)

# Global registry instance
_registry: Optional[SkillsRegistry] = None

def get_registry() -> SkillsRegistry:
    """Get the global skills registry."""
    global _registry
    if _registry is None:
        _registry = SkillsRegistry()
    return _registry

# Example skill factory functions
def create_system_skills(registry: SkillsRegistry):
    """Register built-in system skills."""
    
    async def get_time_handler() -> SkillResult:
        from datetime import datetime
        now = datetime.now()
        return SkillResult(
            success=True,
            output=now.isoformat(),
            evidence=f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
    registry.register(Skill(
        definition=SkillDefinition(
            id="system.get_time",
            name="Get Current Time",
            description="Get the current date and time",
            category=SkillCategory.SYSTEM,
            parameters=[],
            risk_level="low"
        ),
        handler=get_time_handler
    ))
    
    async def get_battery_handler() -> SkillResult:
        import psutil
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return SkillResult(
                    success=True,
                    output={"plugged_in": None, "percent": None},
                    evidence="No battery detected (desktop system)"
                )
            return SkillResult(
                success=True,
                output={
                    "percent": battery.percent,
                    "plugged_in": battery.power_plugged,
                    "time_left": battery.secsleft if battery.secsleft != -1 else None
                },
                evidence=f"Battery: {battery.percent}%, {'charging' if battery.power_plugged else 'discharging'}"
            )
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
            
    registry.register(Skill(
        definition=SkillDefinition(
            id="system.get_battery",
            name="Get Battery Status",
            description="Get current battery status including charge level and power state",
            category=SkillCategory.SYSTEM,
            parameters=[],
            risk_level="low"
        ),
        handler=get_battery_handler
    ))

def create_file_skills(registry: SkillsRegistry):
    """Register file operation skills."""
    
    async def read_file_handler(path: str, limit: int = 10000) -> SkillResult:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(limit)
            return SkillResult(
                success=True,
                output=content,
                evidence=f"Read {len(content)} characters from {path}"
            )
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
            
    registry.register(Skill(
        definition=SkillDefinition(
            id="file.read",
            name="Read File",
            description="Read contents of a file",
            category=SkillCategory.FILE,
            parameters=[
                SkillParameter(
                    name="path",
                    type="string",
                    description="Path to the file",
                    required=True
                ),
                SkillParameter(
                    name="limit",
                    type="integer",
                    description="Maximum characters to read",
                    required=False,
                    default=10000
                )
            ],
            risk_level="low"
        ),
        handler=read_file_handler
    ))

def initialize_default_skills():
    """Initialize the registry with all default skills."""
    registry = get_registry()
    create_system_skills(registry)
    create_file_skills(registry)
    # Additional skill categories can be added here
    logger.info(f"Initialized {len(registry.list_skills())} default skills")
