"""MCP tools API routes."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from backend.mcp.tools.registry import tool_registry

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/tools", response_model=List[Dict[str, Any]])
async def get_tools(resource_type: Optional[str] = Query(None, description="Filter by resource type")):
    """Get all available MCP tools."""
    try:
        tools = tool_registry.get_tools_for_llm()
        
        # Filter by resource type if provided
        if resource_type:
            resource_type_lower = resource_type.lower()
            tools = [
                tool for tool in tools
                if resource_type_lower in tool.get('name', '').lower()
            ]
        
        return tools
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/{tool_name}", response_model=Dict[str, Any])
async def get_tool(tool_name: str):
    """Get specific MCP tool details."""
    try:
        tools = tool_registry.get_tools_for_llm()
        tool = next((t for t in tools if t.get('name') == tool_name), None)
        
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        return tool
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

