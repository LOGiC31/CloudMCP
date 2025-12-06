"""MCP tool registry."""
from typing import List, Dict, Any, Optional
from backend.mcp.tools.base import MCPTool
from backend.mcp.tools.docker_tools import (
    DockerRestartTool,
    DockerScaleTool,
    DockerLogsTool,
    DockerStatsTool
)
from backend.mcp.tools.postgres_tools import (
    PostgresRestartTool,
    PostgresScaleConnectionsTool,
    PostgresVacuumTool,
    PostgresKillLongQueriesTool
)
from backend.mcp.tools.redis_tools import (
    RedisFlushTool,
    RedisRestartTool,
    RedisMemoryPurgeTool,
    RedisInfoTool
)
from backend.mcp.tools.nginx_tools import (
    NginxRestartTool,
    NginxReloadTool,
    NginxScaleConnectionsTool,
    NginxClearConnectionsTool,
    NginxInfoTool
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MCPToolRegistry:
    """Registry for MCP tools."""
    
    def __init__(self):
        """Initialize tool registry with all available tools."""
        self._tools: Dict[str, MCPTool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default MCP tools."""
        # Docker tools
        self.register(DockerRestartTool())
        self.register(DockerScaleTool())
        self.register(DockerLogsTool())
        self.register(DockerStatsTool())
        
        # PostgreSQL tools
        self.register(PostgresRestartTool())
        self.register(PostgresScaleConnectionsTool())
        self.register(PostgresVacuumTool())
        self.register(PostgresKillLongQueriesTool())
        
        # Redis tools
        self.register(RedisFlushTool())
        self.register(RedisRestartTool())
        self.register(RedisMemoryPurgeTool())
        self.register(RedisInfoTool())
        
        # Nginx tools
        self.register(NginxRestartTool())
        self.register(NginxReloadTool())
        self.register(NginxScaleConnectionsTool())
        self.register(NginxClearConnectionsTool())
        self.register(NginxInfoTool())
        
        logger.info(f"Registered {len(self._tools)} MCP tools")
    
    def register(self, tool: MCPTool):
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[MCPTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Get all tools formatted for LLM consumption."""
        return [tool.to_dict() for tool in self._tools.values()]
    
    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name."""
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "message": f"Tool not found: {tool_name}",
                "error": "ToolNotFound"
            }
        
        try:
            result = await tool.execute(params)
            return result.to_dict()
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error executing tool: {str(e)}",
                "error": str(e)
            }


# Global registry instance
tool_registry = MCPToolRegistry()

