"""Docker MCP tools."""
import docker
from typing import Dict, Any
from backend.mcp.tools.base import MCPTool, ToolResult
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DockerRestartTool(MCPTool):
    """Tool to restart a Docker container."""
    
    def __init__(self):
        super().__init__(
            name="docker_restart",
            description="Restart a Docker container by name or ID",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Name or ID of the container to restart",
                    "required": True
                }
            }
        )
        self.client = None
        self._init_docker_client()
    
    def _init_docker_client(self):
        """Initialize Docker client with error handling."""
        try:
            import os
            # Try Colima socket first (most reliable)
            colima_socket = os.path.expanduser("~/.colima/default/docker.sock")
            if os.path.exists(colima_socket):
                self.client = docker.DockerClient(base_url=f"unix://{colima_socket}")
            else:
                # Try default Docker socket
                default_socket = "/var/run/docker.sock"
                if os.path.exists(default_socket):
                    self.client = docker.DockerClient(base_url=f"unix://{default_socket}")
                else:
                    # Fallback to from_env but ignore bad DOCKER_HOST
                    old_docker_host = os.environ.pop("DOCKER_HOST", None)
                    try:
                        self.client = docker.from_env()
                    finally:
                        if old_docker_host:
                            os.environ["DOCKER_HOST"] = old_docker_host
            self.client.ping()
        except Exception as e:
            self.client = None
            logger.warning(f"Docker client not available for docker_restart tool: {e}")
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Restart a Docker container."""
        container_name = params.get("container_name")
        if not container_name:
            return ToolResult(
                success=False,
                message="container_name parameter is required",
                error="Missing required parameter"
            )
        
        # Try Docker client first
        if self.client:
            try:
                container = self.client.containers.get(container_name)
                container.restart()
                logger.info(f"Restarted container: {container_name}")
                return ToolResult(
                    success=True,
                    message=f"Successfully restarted container: {container_name}",
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
                logger.info(f"Restarted container via CLI: {container_name}")
                return ToolResult(
                    success=True,
                    message=f"Successfully restarted container: {container_name}",
                    data={"container_name": container_name}
                )
            else:
                return ToolResult(
                    success=False,
                    message=f"Failed to restart container: {container_name}",
                    error="RestartFailed"
                )
        except Exception as e:
            logger.error(f"Error restarting container: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to restart container: {str(e)}",
                error=str(e)
            )


class DockerScaleTool(MCPTool):
    """Tool to scale Docker containers (using docker-compose)."""
    
    def __init__(self):
        super().__init__(
            name="docker_scale",
            description="Scale a Docker service to a specific number of replicas",
            parameters={
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to scale",
                    "required": True
                },
                "replicas": {
                    "type": "integer",
                    "description": "Number of replicas",
                    "required": True
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Scale Docker service."""
        import subprocess
        
        service_name = params.get("service_name")
        replicas = params.get("replicas")
        
        if not service_name or replicas is None:
            return ToolResult(
                success=False,
                message="service_name and replicas parameters are required",
                error="Missing required parameters"
            )
        
        try:
            # Use docker-compose scale command
            result = subprocess.run(
                ["docker-compose", "up", "-d", "--scale", f"{service_name}={replicas}"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Scaled service {service_name} to {replicas} replicas")
            return ToolResult(
                success=True,
                message=f"Successfully scaled {service_name} to {replicas} replicas",
                data={"service_name": service_name, "replicas": replicas}
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Error scaling service: {e.stderr}")
            return ToolResult(
                success=False,
                message=f"Failed to scale service: {e.stderr}",
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Error scaling service: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to scale service: {str(e)}",
                error=str(e)
            )


class DockerLogsTool(MCPTool):
    """Tool to get Docker container logs."""
    
    def __init__(self):
        super().__init__(
            name="docker_logs",
            description="Get logs from a Docker container",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Name or ID of the container",
                    "required": True
                },
                "tail": {
                    "type": "integer",
                    "description": "Number of lines to return (default: 100)",
                    "required": False
                }
            }
        )
        self.client = None
        self._init_docker_client()
    
    def _init_docker_client(self):
        """Initialize Docker client with error handling."""
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as e:
            self.client = None
            logger.warning(f"Docker client not available for docker_logs tool: {e}")
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Get container logs."""
        container_name = params.get("container_name")
        tail = params.get("tail", 100)
        
        if not container_name:
            return ToolResult(
                success=False,
                message="container_name parameter is required",
                error="Missing required parameter"
            )
        
        # Try Docker client first
        if self.client:
            try:
                container = self.client.containers.get(container_name)
                logs = container.logs(tail=tail, timestamps=True).decode('utf-8')
                return ToolResult(
                    success=True,
                    message=f"Retrieved logs from {container_name}",
                    data={"logs": logs, "container_name": container_name}
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
            from backend.utils.docker_helper import get_container_logs_via_cli
            logs = get_container_logs_via_cli(container_name, tail)
            return ToolResult(
                success=True,
                message=f"Retrieved logs from {container_name}",
                data={"logs": "\n".join(logs), "container_name": container_name}
            )
        except Exception as e:
            logger.error(f"Error getting logs: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to get logs: {str(e)}",
                error=str(e)
            )


class DockerStatsTool(MCPTool):
    """Tool to get Docker container statistics."""
    
    def __init__(self):
        super().__init__(
            name="docker_stats",
            description="Get resource usage statistics for a Docker container",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Name or ID of the container",
                    "required": True
                }
            }
        )
        self.client = None
        self._init_docker_client()
    
    def _init_docker_client(self):
        """Initialize Docker client with error handling."""
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as e:
            self.client = None
            logger.warning(f"Docker client not available for docker_stats tool: {e}")
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Get container stats."""
        container_name = params.get("container_name")
        
        if not container_name:
            return ToolResult(
                success=False,
                message="container_name parameter is required",
                error="Missing required parameter"
            )
        
        # Try Docker client first
        if self.client:
            try:
                container = self.client.containers.get(container_name)
                stats = container.stats(stream=False)
                
                # Extract useful metrics
                cpu_stats = stats.get('cpu_stats', {})
                memory_stats = stats.get('memory_stats', {})
                
                metrics = {
                    "container_name": container_name,
                    "cpu_usage_percent": self._calculate_cpu_percent(stats),
                    "memory_usage_bytes": memory_stats.get('usage', 0),
                    "memory_limit_bytes": memory_stats.get('limit', 0),
                    "memory_usage_percent": (
                        memory_stats.get('usage', 0) / memory_stats.get('limit', 1) * 100
                        if memory_stats.get('limit', 0) > 0 else 0
                    ),
                    "network_rx_bytes": stats.get('networks', {}).get('eth0', {}).get('rx_bytes', 0),
                    "network_tx_bytes": stats.get('networks', {}).get('eth0', {}).get('tx_bytes', 0),
                }
                
                return ToolResult(
                    success=True,
                    message=f"Retrieved stats from {container_name}",
                    data=metrics
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
            from backend.utils.docker_helper import get_container_stats_via_cli
            stats = get_container_stats_via_cli(container_name)
            if stats:
                return ToolResult(
                    success=True,
                    message=f"Retrieved stats from {container_name}",
                    data=stats
                )
            else:
                return ToolResult(
                    success=False,
                    message=f"Failed to get stats for {container_name}",
                    error="StatsUnavailable"
                )
        except Exception as e:
            logger.error(f"Error getting stats: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to get stats: {str(e)}",
                error=str(e)
            )
    
    def _calculate_cpu_percent(self, stats: Dict[str, Any]) -> float:
        """Calculate CPU usage percentage."""
        try:
            cpu_delta = (
                stats['cpu_stats']['cpu_usage']['total_usage'] -
                stats.get('precpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
            )
            system_delta = (
                stats['cpu_stats']['system_cpu_usage'] -
                stats.get('precpu_stats', {}).get('system_cpu_usage', 0)
            )
            num_cpus = stats['cpu_stats'].get('online_cpus', 1)
            
            if system_delta > 0:
                return (cpu_delta / system_delta) * num_cpus * 100.0
            return 0.0
        except (KeyError, ZeroDivisionError):
            return 0.0

