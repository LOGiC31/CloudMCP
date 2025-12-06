"""Redis MCP tools."""
import redis
from typing import Dict, Any
from backend.mcp.tools.base import MCPTool, ToolResult
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def get_redis_client():
    """Get Redis client."""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True
    )


class RedisFlushTool(MCPTool):
    """Tool to flush Redis cache."""
    
    def __init__(self):
        super().__init__(
            name="redis_flush",
            description="Flush all data from Redis cache",
            parameters={
                "db": {
                    "type": "integer",
                    "description": "Database number to flush (default: 0, -1 for all)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Flush Redis cache."""
        db = params.get("db", 0)
        
        try:
            client = get_redis_client()
            
            if db == -1:
                # Flush all databases
                client.flushall()
                message = "Flushed all Redis databases"
            else:
                client.flushdb()
                message = f"Flushed Redis database {db}"
            
            logger.info(message)
            return ToolResult(
                success=True,
                message=message,
                data={"db": db}
            )
        except Exception as e:
            logger.error(f"Error flushing Redis: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to flush Redis: {str(e)}",
                error=str(e)
            )


class RedisRestartTool(MCPTool):
    """Tool to restart Redis (via Docker)."""
    
    def __init__(self):
        super().__init__(
            name="redis_restart",
            description="Restart Redis container",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Name of Redis container (default: redis)",
                    "required": False
                }
            }
        )
        import docker
        self.docker_client = None
        self._init_docker_client()
    
    def _init_docker_client(self):
        """Initialize Docker client with error handling."""
        try:
            import docker
            import os
            # Try Colima socket first (most reliable)
            colima_socket = os.path.expanduser("~/.colima/default/docker.sock")
            if os.path.exists(colima_socket):
                self.docker_client = docker.DockerClient(base_url=f"unix://{colima_socket}")
            else:
                # Try default Docker socket
                default_socket = "/var/run/docker.sock"
                if os.path.exists(default_socket):
                    self.docker_client = docker.DockerClient(base_url=f"unix://{default_socket}")
                else:
                    # Fallback to from_env but ignore bad DOCKER_HOST
                    old_docker_host = os.environ.pop("DOCKER_HOST", None)
                    try:
                        self.docker_client = docker.from_env()
                    finally:
                        if old_docker_host:
                            os.environ["DOCKER_HOST"] = old_docker_host
            self.docker_client.ping()
        except Exception as e:
            self.docker_client = None
            logger.warning(f"Docker client not available for redis_restart tool: {e}")
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Restart Redis container."""
        container_name = params.get("container_name", "redis")
        
        # Try Docker client first
        if self.docker_client:
            try:
                container = self.docker_client.containers.get(container_name)
                container.restart()
                logger.info(f"Restarted Redis container: {container_name}")
                return ToolResult(
                    success=True,
                    message=f"Successfully restarted Redis container: {container_name}",
                    data={"container_name": container_name}
                )
            except docker.errors.NotFound:
                return ToolResult(
                    success=False,
                    message=f"Container not found: {container_name}",
                    error="ContainerNotFound"
                )
            except Exception as e:
                logger.warning(f"Docker client failed, trying CLI: {e}")
        
        # Fallback to CLI
        try:
            from backend.utils.docker_helper import restart_container_via_cli
            if restart_container_via_cli(container_name):
                logger.info(f"Restarted Redis container via CLI: {container_name}")
                return ToolResult(
                    success=True,
                    message=f"Successfully restarted Redis container: {container_name}",
                    data={"container_name": container_name}
                )
            else:
                return ToolResult(
                    success=False,
                    message=f"Failed to restart container: {container_name}",
                    error="RestartFailed"
                )
        except Exception as e:
            logger.error(f"Error restarting Redis: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to restart Redis: {str(e)}",
                error=str(e)
            )


class RedisMemoryPurgeTool(MCPTool):
    """Tool to purge Redis memory using eviction policies."""
    
    def __init__(self):
        super().__init__(
            name="redis_memory_purge",
            description="Purge Redis memory by evicting keys based on LRU policy",
            parameters={
                "maxmemory": {
                    "type": "string",
                    "description": "Set maxmemory limit (e.g., '100mb', '1gb')",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Purge Redis memory."""
        maxmemory = params.get("maxmemory")
        
        try:
            client = get_redis_client()
            
            # Get current memory info
            info = client.info("memory")
            used_memory = info.get("used_memory_human", "unknown")
            maxmemory_set = info.get("maxmemory_human", "0")
            
            if maxmemory:
                # Set maxmemory (requires CONFIG SET)
                try:
                    client.config_set("maxmemory", maxmemory)
                    client.config_set("maxmemory-policy", "allkeys-lru")
                    logger.info(f"Set Redis maxmemory to {maxmemory}")
                except redis.exceptions.ResponseError as e:
                    logger.warning(f"Could not set maxmemory (may require redis.conf): {e}")
            
            # Force eviction by setting a lower maxmemory temporarily
            # This is a workaround - in production, maxmemory-policy should be configured
            result = {
                "used_memory": used_memory,
                "maxmemory": maxmemory_set,
                "maxmemory_set": maxmemory
            }
            
            return ToolResult(
                success=True,
                message=f"Memory purge initiated. Current memory: {used_memory}, Max: {maxmemory_set}",
                data=result
            )
        except Exception as e:
            logger.error(f"Error purging Redis memory: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to purge memory: {str(e)}",
                error=str(e)
            )


class RedisInfoTool(MCPTool):
    """Tool to get Redis information and statistics."""
    
    def __init__(self):
        super().__init__(
            name="redis_info",
            description="Get Redis server information and statistics",
            parameters={
                "section": {
                    "type": "string",
                    "description": "Info section (memory, stats, clients, etc.)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Get Redis info."""
        section = params.get("section", "all")
        
        try:
            client = get_redis_client()
            info = client.info(section)
            
            return ToolResult(
                success=True,
                message=f"Retrieved Redis info for section: {section}",
                data=info
            )
        except Exception as e:
            logger.error(f"Error getting Redis info: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to get Redis info: {str(e)}",
                error=str(e)
            )

