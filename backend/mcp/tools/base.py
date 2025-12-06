"""Base MCP tool interface."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class ToolResult:
    """Result of a tool execution."""
    
    def __init__(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.message = message
        self.data = data or {}
        self.error = error
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp
        }


class MCPTool(ABC):
    """Base class for MCP tools."""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        """
        Initialize MCP tool.
        
        Args:
            name: Tool name
            description: Tool description
            parameters: Tool parameters schema
        """
        self.name = name
        self.description = description
        self.parameters = parameters
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool.
        
        Args:
            params: Tool parameters
            
        Returns:
            ToolResult with execution outcome
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary for LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

