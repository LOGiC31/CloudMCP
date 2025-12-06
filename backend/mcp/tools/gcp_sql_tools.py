"""GCP Cloud SQL MCP tools."""
import asyncio
from typing import Dict, Any
from backend.mcp.tools.base import MCPTool, ToolResult
from backend.gcp.auth import get_gcp_project_id
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GCPSQLRestartInstanceTool(MCPTool):
    """Tool to restart a Cloud SQL instance."""
    
    def __init__(self):
        super().__init__(
            name="gcp_sql_restart_instance",
            description="Restart a Cloud SQL instance. This will cause brief downtime.",
            parameters={
                "instance_id": {
                    "type": "string",
                    "description": "Cloud SQL instance ID",
                    "required": True
                },
                "project_id": {
                    "type": "string",
                    "description": "GCP project ID (default: from config)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Restart a Cloud SQL instance."""
        try:
            from googleapiclient.discovery import build
            from backend.gcp.auth import get_gcp_credentials
            
            instance_id = params.get("instance_id")
            project_id = params.get("project_id") or get_gcp_project_id()
            
            if not settings.GCP_ENABLED:
                return ToolResult(
                    success=False,
                    message="GCP is not enabled. Set GCP_ENABLED=true in config.",
                    error="GCP_DISABLED"
                )
            
            try:
                credentials, _ = get_gcp_credentials()
            except Exception as auth_error:
                error_type = type(auth_error).__name__
                error_str = str(auth_error).lower()
                if 'RefreshError' in error_type or 'access token' in error_str or 'id_token' in error_str:
                    return ToolResult(
                        success=False,
                        message=f"Authentication error: Service account key may be misconfigured. Error: {error_type}",
                        error="AUTH_ERROR"
                    )
                raise
            
            service = build('sqladmin', 'v1', credentials=credentials)
            
            # Restart the instance
            request = service.instances().restart(
                project=project_id,
                instance=instance_id
            )
            
            try:
                operation = await asyncio.to_thread(request.execute)
            except Exception as api_error:
                error_type = type(api_error).__name__
                error_str = str(api_error).lower()
                if 'RefreshError' in error_type or 'access token' in error_str or 'id_token' in error_str:
                    return ToolResult(
                        success=False,
                        message=f"Authentication error during API call: Service account key may be misconfigured. Error: {error_type}",
                        error="AUTH_ERROR"
                    )
                raise
            
            # Wait for operation to complete
            operation_name = operation['name']
            while True:
                op_request = service.operations().get(
                    project=project_id,
                    operation=operation_name
                )
                op_response = await asyncio.to_thread(op_request.execute)
                
                if op_response['status'] == 'DONE':
                    if 'error' in op_response:
                        raise Exception(f"Operation failed: {op_response['error']}")
                    break
                
                await asyncio.sleep(2)
            
            logger.info(f"Cloud SQL instance {instance_id} restarted successfully")
            return ToolResult(
                success=True,
                message=f"Cloud SQL instance {instance_id} restarted successfully",
                data={
                    "instance_id": instance_id,
                    "project_id": project_id
                }
            )
        except Exception as e:
            logger.error(f"Error restarting Cloud SQL instance: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to restart Cloud SQL instance: {str(e)}",
                error=str(e)
            )


class GCPSQLScaleTierTool(MCPTool):
    """Tool to scale Cloud SQL instance tier."""
    
    def __init__(self):
        super().__init__(
            name="gcp_sql_scale_tier",
            description="Change the tier (machine type) of a Cloud SQL instance to scale up/down resources.",
            parameters={
                "instance_id": {
                    "type": "string",
                    "description": "Cloud SQL instance ID",
                    "required": True
                },
                "tier": {
                    "type": "string",
                    "description": "New tier (e.g., 'db-f1-micro', 'db-n1-standard-1', 'db-n1-standard-2')",
                    "required": True
                },
                "project_id": {
                    "type": "string",
                    "description": "GCP project ID (default: from config)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Scale Cloud SQL instance tier."""
        try:
            from googleapiclient.discovery import build
            from backend.gcp.auth import get_gcp_credentials
            
            instance_id = params.get("instance_id")
            tier = params.get("tier")
            project_id = params.get("project_id") or get_gcp_project_id()
            
            if not settings.GCP_ENABLED:
                return ToolResult(
                    success=False,
                    message="GCP is not enabled. Set GCP_ENABLED=true in config.",
                    error="GCP_DISABLED"
                )
            
            credentials, _ = get_gcp_credentials()
            service = build('sqladmin', 'v1', credentials=credentials)
            
            # Get current instance settings
            get_request = service.instances().get(
                project=project_id,
                instance=instance_id
            )
            instance = await asyncio.to_thread(get_request.execute)
            
            # Update tier
            instance['settings']['tier'] = tier
            
            # Patch the instance
            patch_request = service.instances().patch(
                project=project_id,
                instance=instance_id,
                body=instance
            )
            
            operation = await asyncio.to_thread(patch_request.execute)
            
            # Wait for operation
            operation_name = operation['name']
            while True:
                op_request = service.operations().get(
                    project=project_id,
                    operation=operation_name
                )
                op_response = await asyncio.to_thread(op_request.execute)
                
                if op_response['status'] == 'DONE':
                    if 'error' in op_response:
                        raise Exception(f"Operation failed: {op_response['error']}")
                    break
                
                await asyncio.sleep(2)
            
            logger.info(f"Cloud SQL instance {instance_id} scaled to tier {tier} successfully")
            return ToolResult(
                success=True,
                message=f"Cloud SQL instance {instance_id} scaled to tier {tier} successfully",
                data={
                    "instance_id": instance_id,
                    "tier": tier,
                    "project_id": project_id
                }
            )
        except Exception as e:
            logger.error(f"Error scaling Cloud SQL instance: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to scale Cloud SQL instance: {str(e)}",
                error=str(e)
            )


class GCPSQLKillConnectionsTool(MCPTool):
    """Tool to kill long-running queries/connections in Cloud SQL."""
    
    def __init__(self):
        super().__init__(
            name="gcp_sql_kill_connections",
            description="Kill long-running queries or connections in Cloud SQL to free up connection pool.",
            parameters={
                "instance_id": {
                    "type": "string",
                    "description": "Cloud SQL instance ID",
                    "required": True
                },
                "database_name": {
                    "type": "string",
                    "description": "Database name",
                    "required": True
                },
                "duration_seconds": {
                    "type": "integer",
                    "description": "Kill queries running longer than this duration (default: 5 seconds)",
                    "required": False
                },
                "project_id": {
                    "type": "string",
                    "description": "GCP project ID (default: from config)",
                    "required": False
                }
            }
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Kill long-running queries in Cloud SQL."""
        try:
            # Note: This requires connecting to the database directly
            # We'll need to use Cloud SQL Proxy or private IP connection
            # For now, this is a placeholder that would need database connection setup
            
            instance_id = params.get("instance_id")
            database_name = params.get("database_name")
            duration_seconds = params.get("duration_seconds", 5)
            project_id = params.get("project_id") or get_gcp_project_id()
            
            if not settings.GCP_ENABLED:
                return ToolResult(
                    success=False,
                    message="GCP is not enabled. Set GCP_ENABLED=true in config.",
                    error="GCP_DISABLED"
                )
            
            # TODO: Implement actual connection killing via Cloud SQL connection
            # This requires:
            # 1. Cloud SQL Proxy setup or private IP connection
            # 2. Database credentials
            # 3. Execute SQL: SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE ...
            
            logger.warning(f"gcp_sql_kill_connections not fully implemented yet for {instance_id}")
            return ToolResult(
                success=False,
                message="Cloud SQL connection killing requires database connection setup (Cloud SQL Proxy or private IP). Not yet implemented.",
                error="NOT_IMPLEMENTED"
            )
        except Exception as e:
            logger.error(f"Error killing Cloud SQL connections: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to kill connections: {str(e)}",
                error=str(e)
            )

