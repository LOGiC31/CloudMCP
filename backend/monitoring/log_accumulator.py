"""Log accumulator for collecting and aggregating logs."""
import docker
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class LogAccumulator:
    """Accumulates logs from various sources."""
    
    def __init__(self):
        """Initialize log accumulator."""
        self.docker_client = None
        self.logs_cache: List[Dict[str, Any]] = []
        self._init_docker_client()
    
    def _init_docker_client(self):
        """Initialize Docker client with error handling."""
        try:
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
            
            # Test connection
            self.docker_client.ping()
        except docker.errors.DockerException as e:
            self.docker_client = None
            logger.warning(f"Docker not available: {e}. Log collection will be limited.")
        except Exception as e:
            self.docker_client = None
            logger.warning(f"Failed to initialize Docker client: {e}. Log collection will be limited.")
    
    async def collect_logs(
        self,
        resource_type: str,
        resource_id: str,
        tail: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Collect logs from a resource.
        
        Args:
            resource_type: Type of resource (docker, postgres, redis)
            resource_id: Resource identifier (container name, etc.)
            tail: Number of log lines to retrieve
            
        Returns:
            List of log entries
        """
        logs = []
        
        try:
            if resource_type == "docker":
                logs = await self._collect_docker_logs(resource_id, tail)
            elif resource_type == "postgres":
                logs = await self._collect_postgres_logs(resource_id, tail)
            elif resource_type == "redis":
                logs = await self._collect_redis_logs(resource_id, tail)
            else:
                logger.warning(f"Unknown resource type: {resource_type}")
        
        except Exception as e:
            logger.error(f"Error collecting logs from {resource_type}:{resource_id}: {e}", exc_info=True)
        
        return logs
    
    async def _collect_docker_logs(self, container_name: str, tail: int) -> List[Dict[str, Any]]:
        """Collect logs from Docker container."""
        # Try Docker client first
        if self.docker_client:
            try:
                container = self.docker_client.containers.get(container_name)
                log_lines = container.logs(tail=tail, timestamps=True).decode('utf-8').split('\n')
                
                logs = []
                for line in log_lines:
                    if not line.strip():
                        continue
                    
                    # Parse Docker log format: 2024-01-01T12:00:00.000000000Z message
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        timestamp_str, message = parts
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except:
                            timestamp = datetime.utcnow()
                    else:
                        message = line
                        timestamp = datetime.utcnow()
                    
                    # Determine log level
                    level = "INFO"
                    message_upper = message.upper()
                    if "ERROR" in message_upper or "CRITICAL" in message_upper:
                        level = "ERROR"
                    elif "WARNING" in message_upper or "WARN" in message_upper:
                        level = "WARNING"
                    elif "DEBUG" in message_upper:
                        level = "DEBUG"
                    
                    # Also check for load generation messages (these indicate failures)
                    if "generating" in message_upper and ("load" in message_upper or "database" in message_upper or "redis" in message_upper):
                        level = "WARNING"
                    
                    logs.append({
                        "id": f"log_{len(self.logs_cache) + len(logs)}",
                        "timestamp": timestamp.isoformat(),
                        "resource_id": container_name,
                        "resource_type": "docker",
                        "level": level,
                        "message": message,
                        "metadata": {}
                    })
                
                return logs
            except docker.errors.NotFound:
                logger.warning(f"Container not found: {container_name}")
                return []
            except Exception as e:
                logger.warning(f"Docker client failed, trying CLI: {e}")
        
        # Fallback to CLI
        try:
            from backend.utils.docker_helper import get_container_logs_via_cli
            log_lines = get_container_logs_via_cli(container_name, tail)
            
            logs = []
            for line in log_lines:
                if not line.strip():
                    continue
                
                # Parse log line (simplified - Docker CLI format)
                timestamp = datetime.utcnow()
                message = line
                
                # Determine log level
                level = "INFO"
                message_upper = message.upper()
                if "ERROR" in message_upper or "CRITICAL" in message_upper:
                    level = "ERROR"
                elif "WARNING" in message_upper or "WARN" in message_upper:
                    level = "WARNING"
                elif "DEBUG" in message_upper:
                    level = "DEBUG"
                
                logs.append({
                    "id": f"log_{len(self.logs_cache) + len(logs)}",
                    "timestamp": timestamp.isoformat(),
                    "resource_id": container_name,
                    "resource_type": "docker",
                    "level": level,
                    "message": message,
                    "metadata": {}
                })
            
            return logs
        except Exception as e:
            logger.error(f"Error collecting Docker logs: {e}", exc_info=True)
            return []
    
    async def _collect_postgres_logs(self, container_name: str, tail: int) -> List[Dict[str, Any]]:
        """Collect logs from PostgreSQL (via Docker)."""
        # PostgreSQL logs are typically in Docker logs
        return await self._collect_docker_logs(container_name, tail)
    
    async def _collect_redis_logs(self, container_name: str, tail: int) -> List[Dict[str, Any]]:
        """Collect logs from Redis (via Docker)."""
        # Redis logs are typically in Docker logs
        return await self._collect_docker_logs(container_name, tail)
    
    async def get_error_logs(
        self,
        time_range: Optional[Dict[str, Any]] = None,
        resource_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get error logs within a time range.
        
        Args:
            time_range: Dict with 'start' and 'end' ISO datetime strings
            resource_ids: Optional list of resource IDs to filter
            
        Returns:
            List of error log entries
        """
        # Collect fresh logs from all known resources
        all_logs = []
        
        # Get all containers
        containers = []
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list(all=True)
            except Exception as e:
                logger.warning(f"Docker client failed, trying CLI: {e}")
        
        if not containers:
            # Fallback to CLI
            from backend.utils.docker_helper import get_containers_via_cli
            containers_data = get_containers_via_cli()
            # Convert to container-like objects for compatibility
            class ContainerWrapper:
                def __init__(self, data):
                    self.name = data.get("name", "").lstrip("/")
                    self.id = data.get("id", "")
            containers = [ContainerWrapper(c) for c in containers_data]
        
        try:
            # Filter containers first
            filtered_containers = [
                container for container in containers
                if not resource_ids or container.name in resource_ids
            ]
            
            # Collect logs from all containers in parallel
            import asyncio
            log_tasks = [self.collect_logs("docker", container.name, tail=500) for container in filtered_containers]
            log_results = await asyncio.gather(*log_tasks, return_exceptions=True)
            
            # Collect all logs
            for logs in log_results:
                if isinstance(logs, list):
                    all_logs.extend(logs)
                elif isinstance(logs, Exception):
                    logger.debug(f"Error collecting logs: {logs}")
        except Exception as e:
            logger.error(f"Error getting error logs: {e}", exc_info=True)
        
        # Filter error and warning logs (warnings can indicate failures)
        error_logs = [
            log for log in all_logs
            if log.get("level") in ["ERROR", "CRITICAL", "WARNING"]
        ]
        
        # Filter by time range
        if time_range:
            start = datetime.fromisoformat(time_range.get("start", ""))
            end = datetime.fromisoformat(time_range.get("end", ""))
            error_logs = [
                log for log in error_logs
                if start <= datetime.fromisoformat(log["timestamp"]) <= end
            ]
        
        # Sort by timestamp (newest first)
        error_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return error_logs
    
    async def get_application_config(self) -> Dict[str, Any]:
        """Get application configuration."""
        # This would typically read from a config file or environment
        # For now, return a basic structure
        return {
            "application": {
                "name": "sample-app",
                "version": "1.0.0"
            },
            "resources": {
                "postgres": {
                    "host": settings.POSTGRES_HOST,
                    "port": settings.POSTGRES_PORT,
                    "database": settings.POSTGRES_DB
                },
                "redis": {
                    "host": settings.REDIS_HOST,
                    "port": settings.REDIS_PORT
                }
            },
            "docker": {
                "compose_file": "docker-compose.yml"
            }
        }

