"""GCP Memorystore (Redis) MCP tools."""
import asyncio
from typing import Dict, Any
from backend.mcp.tools.base import MCPTool, ToolResult
from backend.gcp.auth import get_gcp_project_id
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GCPRedisFlushTool(MCPTool):
    """Tool to flush all data from Memorystore (Redis) instance."""
    
    def __init__(self):
        super().__init__(
            name="gcp_redis_flush",
            description="Flush all data from a Memorystore (Redis) instance. This clears all keys and frees up memory.",
            parameters={
                "instance_id": {
                    "type": "string",
                    "description": "Memorystore Redis instance ID",
                    "required": True
                },
                "location": {
                    "type": "string",
                    "description": "GCP region/location (default: from config)",
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
        """Flush all data from Memorystore Redis instance."""
        try:
            from google.cloud import redis_v1
            from backend.gcp.auth import get_gcp_credentials
            
            instance_id = params.get("instance_id")
            location = params.get("location", settings.GCP_REGION)
            project_id = params.get("project_id") or get_gcp_project_id()
            
            if not settings.GCP_ENABLED:
                return ToolResult(
                    success=False,
                    message="GCP is not enabled. Set GCP_ENABLED=true in config.",
                    error="GCP_DISABLED"
                )
            
            # Note: Memorystore doesn't have a direct flush API
            # We need to connect to Redis and execute FLUSHALL command
            # This requires Cloud Memorystore Redis connection setup
            
            logger.warning(f"gcp_redis_flush requires Redis connection setup for {instance_id}")
            return ToolResult(
                success=False,
                message="Memorystore Redis flush requires direct Redis connection (via private IP or VPC). Not yet implemented.",
                error="NOT_IMPLEMENTED"
            )
        except Exception as e:
            logger.error(f"Error flushing Memorystore Redis: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to flush Redis: {str(e)}",
                error=str(e)
            )


class GCPRedisRestartTool(MCPTool):
    """Tool to restart a Memorystore (Redis) instance."""
    
    def __init__(self):
        super().__init__(
            name="gcp_redis_restart",
            description="Restart a Memorystore (Redis) instance. NOTE: Only works for STANDARD_HA tier instances. For BASIC tier instances, use gcp_redis_scale_memory instead (scaling memory will restart the instance).",
            parameters={
                "instance_id": {
                    "type": "string",
                    "description": "Memorystore Redis instance ID",
                    "required": True
                },
                "location": {
                    "type": "string",
                    "description": "GCP region/location (default: from config)",
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
        """Restart a Memorystore Redis instance."""
        try:
            from google.cloud import redis_v1
            from backend.gcp.auth import get_gcp_credentials
            
            instance_id = params.get("instance_id")
            location = params.get("location", settings.GCP_REGION)
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
            
            client = redis_v1.CloudRedisClient(credentials=credentials)
            
            # First, try to find the instance by listing instances in common regions
            # This handles cases where the location from config doesn't match
            instance = None
            instance_location = location
            
            # Try the provided location first
            try:
                instance_name = f"projects/{project_id}/locations/{location}/instances/{instance_id}"
                instance = client.get_instance(request={"name": instance_name})
            except Exception as first_error:
                error_str = str(first_error).lower()
                # If location not found, try to discover it by listing instances
                if 'location' in error_str or 'not found' in error_str or 'unauthorized' in error_str:
                    logger.debug(f"Location {location} not found, trying to discover instance location...")
                    # Try common regions
                    common_regions = [settings.GCP_REGION, 'us-central1', 'us-east1', 'us-west1', 'europe-west1', 'asia-east1']
                    for region in common_regions:
                        try:
                            parent = f"projects/{project_id}/locations/{region}"
                            instances = client.list_instances(request={"parent": parent})
                            for inst in instances:
                                if inst.name.split('/')[-1] == instance_id:
                                    instance = inst
                                    instance_location = region
                                    logger.info(f"Found instance {instance_id} in region {region}")
                                    break
                            if instance:
                                break
                        except Exception:
                            continue
                    
                    if not instance:
                        # If still not found, return error with helpful message
                        return ToolResult(
                            success=False,
                            message=f"Could not find Redis instance '{instance_id}' in common regions. Please specify the correct location parameter. Error: {str(first_error)}",
                            error="INSTANCE_NOT_FOUND"
                        )
                else:
                    # Check for auth errors
                    error_type = type(first_error).__name__
                    if 'RefreshError' in error_type or 'access token' in error_str or 'id_token' in error_str:
                        return ToolResult(
                            success=False,
                            message=f"Authentication error: Service account key may be misconfigured. Error: {error_type}",
                            error="AUTH_ERROR"
                        )
                    raise
            
            # Now we have the instance and correct location
            instance_name = f"projects/{project_id}/locations/{instance_location}/instances/{instance_id}"
            
            # Check instance tier
            tier = instance.tier  # BASIC or STANDARD_HA
            if tier == redis_v1.Instance.Tier.BASIC:
                return ToolResult(
                    success=False,
                    message=f"Cannot restart BASIC tier Redis instance. BASIC tier instances don't support failover. Use 'gcp_redis_scale_memory' instead to scale memory (this will restart the instance). Current tier: {tier}",
                    error="BASIC_TIER_NOT_SUPPORTED",
                    data={
                        "instance_id": instance_id,
                        "tier": str(tier),
                        "suggestion": "Use gcp_redis_scale_memory to scale memory, which will restart the instance"
                    }
                )
            
            # For STANDARD_HA tier, use failover_instance
            try:
                operation = client.failover_instance(
                    request={
                        "name": instance_name,
                        "data_protection_mode": redis_v1.FailoverInstanceRequest.DataProtectionMode.LIMITED_DATA_LOSS
                    }
                )
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
            
            # Wait for operation
            operation.result(timeout=300)  # 5 minutes timeout
            
            logger.info(f"Memorystore Redis instance {instance_id} restarted successfully")
            return ToolResult(
                success=True,
                message=f"Memorystore Redis instance {instance_id} restarted successfully",
                data={
                    "instance_id": instance_id,
                    "location": location,
                    "project_id": project_id
                }
            )
        except Exception as e:
            logger.error(f"Error restarting Memorystore Redis: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to restart Redis: {str(e)}",
                error=str(e)
            )


class GCPRedisScaleMemoryTool(MCPTool):
    """Tool to scale Memorystore (Redis) memory size."""
    
    def __init__(self):
        super().__init__(
            name="gcp_redis_scale_memory",
            description="Scale the memory size of a Memorystore (Redis) instance to increase capacity.",
            parameters={
                "instance_id": {
                    "type": "string",
                    "description": "Memorystore Redis instance ID",
                    "required": True
                },
                "memory_size_gb": {
                    "type": "integer",
                    "description": "New memory size in GB (e.g., 2, 4, 8)",
                    "required": True
                },
                "location": {
                    "type": "string",
                    "description": "GCP region/location (default: from config)",
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
        """Scale Memorystore Redis memory size."""
        try:
            from google.cloud import redis_v1
            from backend.gcp.auth import get_gcp_credentials
            
            instance_id = params.get("instance_id")
            memory_size_gb = params.get("memory_size_gb")
            location = params.get("location", settings.GCP_REGION)
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
            
            client = redis_v1.CloudRedisClient(credentials=credentials)
            
            # First, try to find the instance by listing instances in common regions
            # This handles cases where the location from config doesn't match
            instance = None
            instance_location = location
            
            # Try the provided location first
            try:
                instance_name = f"projects/{project_id}/locations/{location}/instances/{instance_id}"
                instance = client.get_instance(request={"name": instance_name})
            except Exception as first_error:
                error_str = str(first_error).lower()
                # If location not found, try to discover it by listing instances
                if 'location' in error_str or 'not found' in error_str or 'unauthorized' in error_str:
                    logger.debug(f"Location {location} not found, trying to discover instance location...")
                    # Try common regions
                    common_regions = [settings.GCP_REGION, 'us-central1', 'us-east1', 'us-west1', 'europe-west1', 'asia-east1']
                    for region in common_regions:
                        try:
                            parent = f"projects/{project_id}/locations/{region}"
                            instances = client.list_instances(request={"parent": parent})
                            for inst in instances:
                                if inst.name.split('/')[-1] == instance_id:
                                    instance = inst
                                    instance_location = region
                                    logger.info(f"Found instance {instance_id} in region {region}")
                                    break
                            if instance:
                                break
                        except Exception:
                            continue
                    
                    if not instance:
                        # If still not found, return error with helpful message
                        return ToolResult(
                            success=False,
                            message=f"Could not find Redis instance '{instance_id}' in common regions. Please specify the correct location parameter. Error: {str(first_error)}",
                            error="INSTANCE_NOT_FOUND"
                        )
                else:
                    # Re-raise if it's a different error
                    raise
            
            # Now we have the instance and correct location
            instance_name = f"projects/{project_id}/locations/{instance_location}/instances/{instance_id}"
            
            # Update memory size
            instance.memory_size_gb = memory_size_gb
            
            # Update the instance
            operation = client.update_instance(
                request={
                    "update_mask": {"paths": ["memory_size_gb"]},
                    "instance": instance
                }
            )
            
            # Wait for operation to complete
            operation.result(timeout=600)  # 10 minutes timeout (memory scaling can take time)
            
            # After operation completes, wait a bit more and check if instance is READY
            # The operation completes, but the instance may still be in UPDATING state
            logger.info(f"Memory scaling operation completed. Checking instance state...")
            await asyncio.sleep(5)  # Brief wait for state to update
            
            # Check instance state - it may still be UPDATING
            try:
                updated_instance = client.get_instance(request={"name": instance_name})
                state = updated_instance.state
                state_str = str(state) if hasattr(state, 'name') else str(state)
                
                if 'UPDATING' in state_str or state_str == '2':  # State.UPDATING = 2
                    logger.info(f"Instance is still UPDATING. This is normal - scaling takes time. Instance will be READY shortly.")
                    return ToolResult(
                        success=True,
                        message=f"Memorystore Redis instance {instance_id} scaling to {memory_size_gb}GB initiated successfully. Instance is currently UPDATING and will be READY shortly (this may take a few minutes).",
                        data={
                            "instance_id": instance_id,
                            "memory_size_gb": memory_size_gb,
                            "location": instance_location,
                            "project_id": project_id,
                            "current_state": state_str,
                            "note": "Instance is in UPDATING state. Status will change to HEALTHY once scaling completes."
                        }
                    )
                else:
                    logger.info(f"Memorystore Redis instance {instance_id} scaled to {memory_size_gb}GB successfully (state: {state_str})")
                    return ToolResult(
                        success=True,
                        message=f"Memorystore Redis instance {instance_id} scaled to {memory_size_gb}GB successfully",
                        data={
                            "instance_id": instance_id,
                            "memory_size_gb": memory_size_gb,
                            "location": instance_location,
                            "project_id": project_id,
                            "current_state": state_str
                        }
                    )
            except Exception as check_error:
                # If we can't check state, still return success (operation completed)
                logger.warning(f"Could not verify instance state after scaling: {check_error}")
                return ToolResult(
                    success=True,
                    message=f"Memorystore Redis instance {instance_id} scaling to {memory_size_gb}GB operation completed. Instance may still be updating.",
                    data={
                        "instance_id": instance_id,
                        "memory_size_gb": memory_size_gb,
                        "location": instance_location,
                        "project_id": project_id,
                        "note": "Could not verify final state - instance may still be updating"
                    }
                )
        except Exception as e:
            logger.error(f"Error scaling Memorystore Redis: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"Failed to scale Redis: {str(e)}",
                error=str(e)
            )

