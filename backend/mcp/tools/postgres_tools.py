"""PostgreSQL MCP tools."""
import psycopg2
from typing import Dict, Any
from backend.mcp.tools.base import MCPTool, ToolResult
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def get_postgres_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB
    )


class PostgresRestartTool(MCPTool):
    """Tool to restart PostgreSQL (via Docker)."""
    
    def __init__(self):
        super().__init__(
            name="postgres_restart",
            description="Restart PostgreSQL database container",
            parameters={
                "container_name": {
                    "type": "string",
                    "description": "Name of PostgreSQL container (default: postgres)",
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
            logger.warning(f"Docker client not available for postgres_restart tool: {e}")
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Restart PostgreSQL container."""
        container_name = params.get("container_name", "postgres")
        
        # Try Docker client first
        if self.docker_client:
            try:
                container = self.docker_client.containers.get(container_name)
                container.restart()
                logger.info(f"Restarted PostgreSQL container: {container_name}")
                return ToolResult(
                    success=True,
                    message=f"Successfully restarted PostgreSQL container: {container_name}",
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
                logger.info(f"Restarted PostgreSQL container via CLI: {container_name}")
                return ToolResult(
                    success=True,
                    message=f"Successfully restarted PostgreSQL container: {container_name}",
                    data={"container_name": container_name}
                )
            else:
                return ToolResult(
                    success=False,
                    message=f"Failed to restart container: {container_name}",
                    error="RestartFailed"
                )
        except Exception as e:
            logger.error(f"Error restarting PostgreSQL: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to restart PostgreSQL: {str(e)}",
                error=str(e)
            )


class PostgresScaleConnectionsTool(MCPTool):
    """Tool to modify PostgreSQL connection settings."""
    
    def __init__(self):
        super().__init__(
            name="postgres_scale_connections",
            description="⚠️ WARNING: This tool does NOT work immediately. It only logs a request. Changing max_connections requires modifying postgresql.conf and restarting the container, which is not automated. For immediate connection overload issues, use 'postgres_kill_long_queries' instead to kill blocking queries.",
            parameters={
                "max_connections": {
                    "type": "integer",
                    "description": "New max_connections value (NOTE: This will NOT take effect immediately - requires manual config change and restart)",
                    "required": True
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Modify PostgreSQL max_connections."""
        max_connections = params.get("max_connections")
        
        if not max_connections or max_connections < 1:
            return ToolResult(
                success=False,
                message="max_connections must be a positive integer",
                error="Invalid parameter"
            )
        
        try:
            conn = get_postgres_connection()
            cursor = conn.cursor()
            
            # Set max_connections (requires superuser and restart, so we'll just log it)
            # In production, this would modify postgresql.conf and restart
            cursor.execute("SHOW max_connections;")
            current_max = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            logger.warning(f"max_connections change requested to {max_connections} (current: {current_max}). "
                         f"This requires postgresql.conf modification and restart.")
            
            return ToolResult(
                success=True,
                message=f"max_connections change requested to {max_connections} (current: {current_max}). "
                       f"Note: This requires configuration file change and container restart.",
                data={"requested_max_connections": max_connections, "current_max_connections": current_max}
            )
        except Exception as e:
            logger.error(f"Error modifying PostgreSQL connections: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to modify connections: {str(e)}",
                error=str(e)
            )


class PostgresVacuumTool(MCPTool):
    """Tool to run VACUUM on PostgreSQL database."""
    
    def __init__(self):
        super().__init__(
            name="postgres_vacuum",
            description="Run VACUUM on PostgreSQL database to reclaim storage",
            parameters={
                "table_name": {
                    "type": "string",
                    "description": "Table name (optional, if not provided, vacuums all tables)",
                    "required": False
                },
                "analyze": {
                    "type": "boolean",
                    "description": "Also run ANALYZE (default: true)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Run VACUUM."""
        table_name = params.get("table_name")
        analyze = params.get("analyze", True)
        
        try:
            conn = get_postgres_connection()
            cursor = conn.cursor()
            
            if table_name:
                query = f"VACUUM {'ANALYZE' if analyze else ''} {table_name};"
            else:
                query = f"VACUUM {'ANALYZE' if analyze else ''};"
            
            cursor.execute(query)
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Ran VACUUM{' ANALYZE' if analyze else ''} on {table_name or 'all tables'}")
            return ToolResult(
                success=True,
                message=f"Successfully ran VACUUM{' ANALYZE' if analyze else ''} on {table_name or 'all tables'}",
                data={"table_name": table_name, "analyze": analyze}
            )
        except Exception as e:
            logger.error(f"Error running VACUUM: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to run VACUUM: {str(e)}",
                error=str(e)
            )


class PostgresKillLongQueriesTool(MCPTool):
    """Tool to kill long-running queries."""
    
    def __init__(self):
        super().__init__(
            name="postgres_kill_long_queries",
            description="Kill queries running longer than specified duration",
            parameters={
                "duration_seconds": {
                    "type": "integer",
                    "description": "Kill queries running longer than this (seconds)",
                    "required": True
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Kill long-running queries."""
        duration_seconds = params.get("duration_seconds", 5)  # Default to 5 seconds to catch blocking queries
        
        try:
            # Use Docker exec instead of direct connection to avoid connection issues
            import subprocess
            
            # First, find long-running queries
            find_query = f"""
SELECT pid FROM pg_stat_activity
WHERE state = 'active' 
  AND now() - query_start > interval '{duration_seconds} seconds'
  AND pid != pg_backend_pid();
"""
            
            result = subprocess.run(
                ["docker", "exec", "postgres", "psql", "-U", "postgres", "-d", "sample_app",
                 "-t", "-c", find_query],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    message=f"Failed to find queries: {result.stderr}",
                    error=result.stderr
                )
            
            # Parse PIDs
            pids = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            
            if not pids:
                return ToolResult(
                    success=True,
                    message="No long-running queries found to kill",
                    data={"killed_pids": [], "total_found": 0}
                )
            
            # Kill each query
            killed_pids = []
            for pid in pids:
                try:
                    kill_result = subprocess.run(
                        ["docker", "exec", "postgres", "psql", "-U", "postgres", "-d", "sample_app",
                         "-t", "-c", f"SELECT pg_terminate_backend({pid});"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if kill_result.returncode == 0:
                        killed_pids.append(pid)
                        logger.info(f"Killed query with PID {pid}")
                except Exception as e:
                    logger.warning(f"Failed to kill query {pid}: {e}")
            
            return ToolResult(
                success=True,
                message=f"Killed {len(killed_pids)} long-running queries (found {len(pids)} total)",
                data={"killed_pids": killed_pids, "total_found": len(pids)}
            )
        except Exception as e:
            logger.error(f"Error killing queries: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to kill queries: {str(e)}",
                error=str(e)
            )

