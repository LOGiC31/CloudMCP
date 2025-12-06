"""GCP Compute Engine MCP tools."""
import asyncio
from typing import Dict, Any
from backend.mcp.tools.base import MCPTool, ToolResult
from backend.gcp.auth import get_gcp_project_id
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GCPComputeRestartInstanceTool(MCPTool):
    """Tool to restart a Compute Engine VM instance."""
    
    def __init__(self):
        super().__init__(
            name="gcp_compute_restart_instance",
            description="Restart a Compute Engine VM instance. This will reboot the instance, which may cause brief downtime.",
            parameters={
                "instance_name": {
                    "type": "string",
                    "description": "Name of the Compute Engine instance to restart",
                    "required": True
                },
                "zone": {
                    "type": "string",
                    "description": "GCP zone where the instance is located (default: from config)",
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
        """Restart a Compute Engine instance."""
        try:
            from google.cloud import compute_v1
            from backend.gcp.auth import get_gcp_credentials
            
            instance_name = params.get("instance_name")
            zone = params.get("zone", settings.GCP_ZONE)
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
                if 'RefreshError' in str(type(auth_error).__name__) or 'access token' in str(auth_error).lower():
                    return ToolResult(
                        success=False,
                        message=f"Authentication error: Service account key may be misconfigured. Error: {type(auth_error).__name__}",
                        error="AUTH_ERROR"
                    )
                raise
            
            client = compute_v1.InstancesClient(credentials=credentials)
            
            # Reset (restart) the instance
            request = compute_v1.ResetInstanceRequest(
                project=project_id,
                zone=zone,
                instance=instance_name
            )
            
            try:
                operation = client.reset(request=request)
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
            operation_client = compute_v1.ZoneOperationsClient(credentials=credentials)
            operation_request = compute_v1.WaitZoneOperationRequest(
                operation=operation.name,
                project=project_id,
                zone=zone
            )
            
            # Wait for operation (with timeout)
            await asyncio.to_thread(
                operation_client.wait,
                request=operation_request,
                timeout=300  # 5 minutes timeout
            )
            
            logger.info(f"Compute Engine instance {instance_name} restarted successfully")
            return ToolResult(
                success=True,
                message=f"Compute Engine instance {instance_name} restarted successfully",
                data={
                    "instance_name": instance_name,
                    "zone": zone,
                    "project_id": project_id
                }
            )
        except Exception as e:
            logger.error(f"Error restarting Compute Engine instance: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to restart instance: {str(e)}",
                error=str(e)
            )


class GCPComputeScaleInstanceTool(MCPTool):
    """Tool to scale (change machine type) a Compute Engine instance."""
    
    def __init__(self):
        super().__init__(
            name="gcp_compute_scale_instance",
            description="Change the machine type of a Compute Engine instance (scale up/down). This requires stopping the instance first.",
            parameters={
                "instance_name": {
                    "type": "string",
                    "description": "Name of the Compute Engine instance",
                    "required": True
                },
                "machine_type": {
                    "type": "string",
                    "description": "New machine type (e.g., 'e2-small', 'e2-medium', 'e2-standard-2')",
                    "required": True
                },
                "zone": {
                    "type": "string",
                    "description": "GCP zone where the instance is located (default: from config)",
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
        """Scale a Compute Engine instance."""
        try:
            from google.cloud import compute_v1
            from backend.gcp.auth import get_gcp_credentials
            
            instance_name = params.get("instance_name")
            machine_type = params.get("machine_type")
            zone = params.get("zone", settings.GCP_ZONE)
            project_id = params.get("project_id") or get_gcp_project_id()
            
            if not settings.GCP_ENABLED:
                return ToolResult(
                    success=False,
                    message="GCP is not enabled. Set GCP_ENABLED=true in config.",
                    error="GCP_DISABLED"
                )
            
            credentials, _ = get_gcp_credentials()
            client = compute_v1.InstancesClient(credentials=credentials)
            operation_client = compute_v1.ZoneOperationsClient(credentials=credentials)
            
            # Get current instance to check if it's running
            get_request = compute_v1.GetInstanceRequest(
                project=project_id,
                zone=zone,
                instance=instance_name
            )
            instance = client.get(request=get_request)
            
            was_running = instance.status == compute_v1.Instance.Status.RUNNING
            
            # Stop instance if running (required for machine type change)
            if was_running:
                logger.info(f"Stopping instance {instance_name} before scaling...")
                stop_request = compute_v1.StopInstanceRequest(
                    project=project_id,
                    zone=zone,
                    instance=instance_name
                )
                stop_operation = client.stop(request=stop_request)
                
                # Wait for stop operation
                await asyncio.to_thread(
                    operation_client.wait,
                    request=compute_v1.WaitZoneOperationRequest(
                        operation=stop_operation.name,
                        project=project_id,
                        zone=zone
                    ),
                    timeout=300
                )
            
            # Set machine type
            machine_type_url = f"zones/{zone}/machineTypes/{machine_type}"
            set_machine_type_request = compute_v1.SetMachineTypeInstanceRequest(
                project=project_id,
                zone=zone,
                instance=instance_name,
                instances_set_machine_type_request_resource=compute_v1.InstancesSetMachineTypeRequest(
                    machine_type=machine_type_url
                )
            )
            
            operation = client.set_machine_type(request=set_machine_type_request)
            
            # Wait for operation
            await asyncio.to_thread(
                operation_client.wait,
                request=compute_v1.WaitZoneOperationRequest(
                    operation=operation.name,
                    project=project_id,
                    zone=zone
                ),
                timeout=300
            )
            
            # Start instance if it was running before
            if was_running:
                logger.info(f"Starting instance {instance_name} after scaling...")
                start_request = compute_v1.StartInstanceRequest(
                    project=project_id,
                    zone=zone,
                    instance=instance_name
                )
                start_operation = client.start(request=start_request)
                
                # Wait for start operation
                await asyncio.to_thread(
                    operation_client.wait,
                    request=compute_v1.WaitZoneOperationRequest(
                        operation=start_operation.name,
                        project=project_id,
                        zone=zone
                    ),
                    timeout=300
                )
            
            logger.info(f"Compute Engine instance {instance_name} scaled to {machine_type} successfully")
            return ToolResult(
                success=True,
                message=f"Compute Engine instance {instance_name} scaled to {machine_type} successfully",
                data={
                    "instance_name": instance_name,
                    "machine_type": machine_type,
                    "zone": zone,
                    "project_id": project_id
                }
            )
        except Exception as e:
            logger.error(f"Error scaling Compute Engine instance: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to scale instance: {str(e)}",
                error=str(e)
            )


class GCPComputeStartInstanceTool(MCPTool):
    """Tool to start a stopped Compute Engine instance."""
    
    def __init__(self):
        super().__init__(
            name="gcp_compute_start_instance",
            description="Start a stopped Compute Engine VM instance.",
            parameters={
                "instance_name": {
                    "type": "string",
                    "description": "Name of the Compute Engine instance to start",
                    "required": True
                },
                "zone": {
                    "type": "string",
                    "description": "GCP zone where the instance is located (default: from config)",
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
        """Start a Compute Engine instance."""
        try:
            from google.cloud import compute_v1
            from backend.gcp.auth import get_gcp_credentials
            
            instance_name = params.get("instance_name")
            zone = params.get("zone", settings.GCP_ZONE)
            project_id = params.get("project_id") or get_gcp_project_id()
            
            if not settings.GCP_ENABLED:
                return ToolResult(
                    success=False,
                    message="GCP is not enabled. Set GCP_ENABLED=true in config.",
                    error="GCP_DISABLED"
                )
            
            credentials, _ = get_gcp_credentials()
            client = compute_v1.InstancesClient(credentials=credentials)
            operation_client = compute_v1.ZoneOperationsClient(credentials=credentials)
            
            # Start the instance
            request = compute_v1.StartInstanceRequest(
                project=project_id,
                zone=zone,
                instance=instance_name
            )
            
            operation = client.start(request=request)
            
            # Wait for operation
            await asyncio.to_thread(
                operation_client.wait,
                request=compute_v1.WaitZoneOperationRequest(
                    operation=operation.name,
                    project=project_id,
                    zone=zone
                ),
                timeout=300
            )
            
            logger.info(f"Compute Engine instance {instance_name} started successfully")
            return ToolResult(
                success=True,
                message=f"Compute Engine instance {instance_name} started successfully",
                data={
                    "instance_name": instance_name,
                    "zone": zone,
                    "project_id": project_id
                }
            )
        except Exception as e:
            logger.error(f"Error starting Compute Engine instance: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to start instance: {str(e)}",
                error=str(e)
            )


class GCPComputeStopInstanceTool(MCPTool):
    """Tool to stop a Compute Engine instance."""
    
    def __init__(self):
        super().__init__(
            name="gcp_compute_stop_instance",
            description="Stop a running Compute Engine VM instance. Useful for cost optimization.",
            parameters={
                "instance_name": {
                    "type": "string",
                    "description": "Name of the Compute Engine instance to stop",
                    "required": True
                },
                "zone": {
                    "type": "string",
                    "description": "GCP zone where the instance is located (default: from config)",
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
        """Stop a Compute Engine instance."""
        try:
            from google.cloud import compute_v1
            from backend.gcp.auth import get_gcp_credentials
            
            instance_name = params.get("instance_name")
            zone = params.get("zone", settings.GCP_ZONE)
            project_id = params.get("project_id") or get_gcp_project_id()
            
            if not settings.GCP_ENABLED:
                return ToolResult(
                    success=False,
                    message="GCP is not enabled. Set GCP_ENABLED=true in config.",
                    error="GCP_DISABLED"
                )
            
            credentials, _ = get_gcp_credentials()
            client = compute_v1.InstancesClient(credentials=credentials)
            operation_client = compute_v1.ZoneOperationsClient(credentials=credentials)
            
            # Stop the instance
            request = compute_v1.StopInstanceRequest(
                project=project_id,
                zone=zone,
                instance=instance_name
            )
            
            operation = client.stop(request=request)
            
            # Wait for operation
            await asyncio.to_thread(
                operation_client.wait,
                request=compute_v1.WaitZoneOperationRequest(
                    operation=operation.name,
                    project=project_id,
                    zone=zone
                ),
                timeout=300
            )
            
            logger.info(f"Compute Engine instance {instance_name} stopped successfully")
            return ToolResult(
                success=True,
                message=f"Compute Engine instance {instance_name} stopped successfully",
                data={
                    "instance_name": instance_name,
                    "zone": zone,
                    "project_id": project_id
                }
            )
        except Exception as e:
            logger.error(f"Error stopping Compute Engine instance: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to stop instance: {str(e)}",
                error=str(e)
            )

