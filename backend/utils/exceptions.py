"""Custom exceptions."""


class OrchestrationError(Exception):
    """Base exception for orchestration errors."""
    pass


class LLMError(OrchestrationError):
    """Exception raised for LLM-related errors."""
    pass


class MCPToolError(OrchestrationError):
    """Exception raised for MCP tool execution errors."""
    pass


class ResourceMonitorError(OrchestrationError):
    """Exception raised for resource monitoring errors."""
    pass

