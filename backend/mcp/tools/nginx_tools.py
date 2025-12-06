"""MCP tools for Nginx operations."""
import asyncio
import subprocess
from typing import Dict, Any
from backend.mcp.tools.base import MCPTool, ToolResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class NginxRestartTool(MCPTool):
    """Tool to restart Nginx container."""
    
    def __init__(self):
        super().__init__(
            name="nginx_restart",
            description="Restart the Nginx container to apply configuration changes or recover from issues. NOTE: This does NOT clear active connections from clients. For connection overload issues, use `nginx_clear_connections` or `nginx_reload` instead.",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Nginx container name (default: nginx)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Restart Nginx container."""
        container_name = params.get("container_name", "nginx")
        
        try:
            result = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Nginx container {container_name} restarted successfully")
                return ToolResult(
                    success=True,
                    message=f"Nginx container {container_name} restarted successfully",
                    data={"container": container_name}
                )
            else:
                logger.error(f"Failed to restart Nginx: {result.stderr}")
                return ToolResult(
                    success=False,
                    message=f"Failed to restart Nginx: {result.stderr}",
                    error=result.stderr
                )
        except subprocess.TimeoutExpired:
            logger.error("Nginx restart timed out")
            return ToolResult(
                success=False,
                message="Nginx restart operation timed out",
                error="Timeout"
            )
        except Exception as e:
            logger.error(f"Error restarting Nginx: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Error restarting Nginx: {str(e)}",
                error=str(e)
            )


class NginxReloadTool(MCPTool):
    """Tool to reload Nginx configuration without downtime."""
    
    def __init__(self):
        super().__init__(
            name="nginx_reload",
            description="Reload Nginx configuration without stopping the service. This is preferred over restart for configuration changes.",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Nginx container name (default: nginx)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Reload Nginx configuration."""
        container_name = params.get("container_name", "nginx")
        
        try:
            result = subprocess.run(
                ["docker", "exec", container_name, "nginx", "-s", "reload"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Nginx configuration reloaded successfully for {container_name}")
                return ToolResult(
                    success=True,
                    message=f"Nginx configuration reloaded successfully",
                    data={"container": container_name}
                )
            else:
                logger.error(f"Failed to reload Nginx: {result.stderr}")
                return ToolResult(
                    success=False,
                    message=f"Failed to reload Nginx: {result.stderr}",
                    error=result.stderr
                )
        except subprocess.TimeoutExpired:
            logger.error("Nginx reload timed out")
            return ToolResult(
                success=False,
                message="Nginx reload operation timed out",
                error="Timeout"
            )
        except Exception as e:
            logger.error(f"Error reloading Nginx: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Error reloading Nginx: {str(e)}",
                error=str(e)
            )


class NginxScaleConnectionsTool(MCPTool):
    """Tool to modify Nginx worker_connections setting."""
    
    def __init__(self):
        super().__init__(
            name="nginx_scale_connections",
            description="Modify Nginx worker_connections setting to increase connection capacity. This is the PRIMARY solution for connection overload when load generation is active. Updates config file and reloads Nginx. Use values like 200-300 to handle high connection loads.",
            parameters={
                "worker_connections": {
                    "type": "integer",
                    "description": "New worker_connections value (default: 100)",
                    "required": True
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Modify Nginx worker_connections."""
        worker_connections = params.get("worker_connections", 100)
        
        try:
            # Read current config
            with open("nginx/nginx.conf", "r") as f:
                config = f.read()
            
            # Update worker_connections
            import re
            config = re.sub(
                r'worker_connections\s+\d+;',
                f'worker_connections {worker_connections};',
                config
            )
            
            # Write updated config
            with open("nginx/nginx.conf", "w") as f:
                f.write(config)
            
            # Reload Nginx
            reload_result = subprocess.run(
                ["docker", "exec", "nginx", "nginx", "-s", "reload"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if reload_result.returncode == 0:
                logger.info(f"Nginx worker_connections updated to {worker_connections}")
                return ToolResult(
                    success=True,
                    message=f"Nginx worker_connections updated to {worker_connections} and configuration reloaded",
                    data={"worker_connections": worker_connections}
                )
            else:
                logger.error(f"Failed to reload Nginx after config update: {reload_result.stderr}")
                return ToolResult(
                    success=False,
                    message=f"Config updated but reload failed: {reload_result.stderr}",
                    error=reload_result.stderr
                )
        except Exception as e:
            logger.error(f"Error scaling Nginx connections: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Error scaling Nginx connections: {str(e)}",
                error=str(e)
            )


class NginxClearConnectionsTool(MCPTool):
    """Tool to clear active connections by reloading Nginx."""
    
    def __init__(self):
        super().__init__(
            name="nginx_clear_connections",
            description="Clear active connections by reloading Nginx. This gracefully closes existing connections temporarily. NOTE: If load generation is still active, connections will reconnect. For persistent connection overload, use `nginx_scale_connections` instead to increase capacity.",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Nginx container name (default: nginx)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Clear Nginx connections by reloading and waiting for connections to close."""
        container_name = params.get("container_name", "nginx")
        
        try:
            # Step 1: Reload to gracefully close connections
            result = subprocess.run(
                ["docker", "exec", container_name, "nginx", "-s", "reload"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to reload Nginx: {result.stderr}")
                return ToolResult(
                    success=False,
                    message=f"Failed to reload Nginx: {result.stderr}",
                    error=result.stderr
                )
            
            logger.info(f"Nginx reloaded successfully for {container_name}")
            
            # Step 2: Wait for connections to close gracefully
            # Nginx reload sends SIGUSR2 which gracefully closes connections
            # However, persistent connections from sample-app may take longer to close
            # We'll wait and check connection count multiple times
            max_wait_attempts = 6  # 6 attempts = 12 seconds total
            wait_interval = 2  # Check every 2 seconds
            
            for attempt in range(max_wait_attempts):
                await asyncio.sleep(wait_interval)
                
                # Check current connection count
                check_result = subprocess.run(
                    ["docker", "exec", container_name, "sh", "-c",
                     "netstat -an 2>/dev/null | grep :80 | grep ESTABLISHED | wc -l || ss -tn state established '( dport = :80 )' 2>/dev/null | tail -n +2 | wc -l || echo 0"],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                
                if check_result.returncode == 0:
                    try:
                        conn_count = int(check_result.stdout.strip() or 0)
                        logger.debug(f"Connection check attempt {attempt + 1}: {conn_count} active connections")
                        
                        # If connections are below threshold (20% of limit = 20 connections), consider it successful
                        if conn_count < 20:
                            logger.info(f"Nginx connections cleared: {conn_count} active connections remaining (below threshold)")
                            return ToolResult(
                                success=True,
                                message=f"Nginx connections cleared successfully. {conn_count} active connections remaining (below threshold).",
                                data={"container": container_name, "active_connections": conn_count}
                            )
                    except ValueError:
                        pass
            
            # After max wait, connections may still be high due to persistent load generation
            # This is expected if sample-app is still generating load
            logger.warning(f"Nginx reloaded but connections may still be high due to persistent load generation")
            return ToolResult(
                success=True,
                message=f"Nginx reloaded successfully. Note: Connections may remain high if load generation is still active. Consider stopping the load source.",
                data={"container": container_name, "warning": "Persistent load may cause connections to remain high"}
            )
        except Exception as e:
            logger.error(f"Error clearing Nginx connections: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Error clearing Nginx connections: {str(e)}",
                error=str(e)
            )


class NginxInfoTool(MCPTool):
    """Tool to get Nginx status and connection information."""
    
    def __init__(self):
        super().__init__(
            name="nginx_info",
            description="Get Nginx status, active connections, and configuration information.",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Nginx container name (default: nginx)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Get Nginx information."""
        container_name = params.get("container_name", "nginx")
        
        try:
            # Get Nginx status
            status_result = subprocess.run(
                ["docker", "exec", container_name, "nginx", "-t"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Get active connections (if status module is available)
            conn_result = subprocess.run(
                ["docker", "exec", container_name, "wget", "-qO-", "http://localhost/nginx_status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            info = {
                "container": container_name,
                "config_valid": status_result.returncode == 0,
                "config_output": status_result.stdout,
            }
            
            if conn_result.returncode == 0:
                info["status"] = conn_result.stdout
            
            logger.info(f"Retrieved Nginx info for {container_name}")
            return ToolResult(
                success=True,
                message="Nginx information retrieved successfully",
                data=info
            )
        except Exception as e:
            logger.error(f"Error getting Nginx info: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Error getting Nginx info: {str(e)}",
                error=str(e)
            )

