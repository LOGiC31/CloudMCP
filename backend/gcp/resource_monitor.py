"""GCP resource monitoring."""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.gcp.auth import get_gcp_project_id
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GCPResourceMonitor:
    """Monitor GCP resources (Compute Engine, Cloud SQL, Memorystore)."""
    
    def __init__(self):
        """Initialize GCP resource monitor."""
        self.project_id: Optional[str] = None
        self._compute_client = None
        self._sql_client = None
        self._redis_client = None
        self._monitoring_client = None
        
        if settings.GCP_ENABLED:
            try:
                self.project_id = get_gcp_project_id()
                logger.info(f"GCP Resource Monitor initialized for project: {self.project_id}")
            except Exception as e:
                logger.warning(f"GCP not properly configured: {e}. GCP features will be disabled.")
                settings.GCP_ENABLED = False
    
    def _get_compute_client(self):
        """Get Compute Engine client (lazy initialization)."""
        if not settings.GCP_ENABLED:
            return None
        
        if self._compute_client is None:
            try:
                from google.cloud import compute_v1
                from backend.gcp.auth import get_gcp_credentials
                
                credentials, _ = get_gcp_credentials()
                self._compute_client = compute_v1.InstancesClient(credentials=credentials)
                logger.debug("Compute Engine client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Compute Engine client: {e}", exc_info=True)
                return None
        
        return self._compute_client
    
    def _get_sql_client(self):
        """Get Cloud SQL client (lazy initialization)."""
        if not settings.GCP_ENABLED:
            return None
        
        if self._sql_client is None:
            try:
                from backend.gcp.auth import get_gcp_credentials
                # Cloud SQL Admin API client (uses google-api-python-client)
                from googleapiclient.discovery import build
                
                # Try service account key first
                try:
                    credentials, _ = get_gcp_credentials()
                    self._sql_client = build('sqladmin', 'v1', credentials=credentials)
                    logger.debug("Cloud SQL client initialized with service account key")
                except Exception as sa_error:
                    # If service account fails, try Application Default Credentials
                    error_type = type(sa_error).__name__
                    error_str = str(sa_error).lower()
                    if 'RefreshError' in error_type or 'access token' in error_str or 'id_token' in error_str:
                        logger.debug("Service account key failed for Cloud SQL API, trying Application Default Credentials...")
                        try:
                            from google.auth import default
                            adc_credentials, _ = default(scopes=[
                                'https://www.googleapis.com/auth/cloud-platform',
                                'https://www.googleapis.com/auth/sqlservice.admin',
                            ])
                            self._sql_client = build('sqladmin', 'v1', credentials=adc_credentials)
                            logger.info("Cloud SQL client initialized with Application Default Credentials")
                        except Exception as adc_error:
                            logger.debug(f"ADC also failed for Cloud SQL: {adc_error}")
                            self._sql_client = False
                    else:
                        raise  # Re-raise if it's a different error
                        
            except Exception as e:
                # Check if it's an auth error - if so, don't log as error, just return None
                error_type = type(e).__name__
                error_str = str(e).lower()
                if 'RefreshError' in error_type or 'access token' in error_str or 'id_token' in error_str:
                    logger.debug(f"Cloud SQL client initialization failed due to auth error. Try: gcloud auth application-default login")
                    self._sql_client = False  # Mark as failed to avoid retrying
                else:
                    logger.error(f"Failed to initialize Cloud SQL client: {e}", exc_info=True)
                    self._sql_client = False  # Mark as failed to avoid retrying
        
        # Return None if initialization failed (marked as False)
        return self._sql_client if self._sql_client is not False else None
    
    def _get_redis_client(self):
        """Get Memorystore (Redis) client (lazy initialization)."""
        if not settings.GCP_ENABLED:
            return None
        
        if self._redis_client is None:
            try:
                from google.cloud import redis_v1
                from backend.gcp.auth import get_gcp_credentials
                
                credentials, _ = get_gcp_credentials()
                self._redis_client = redis_v1.CloudRedisClient(credentials=credentials)
                logger.debug("Memorystore (Redis) client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Memorystore client: {e}", exc_info=True)
                return None
        
        return self._redis_client
    
    def _get_monitoring_client(self):
        """Get Cloud Monitoring client (lazy initialization)."""
        if not settings.GCP_ENABLED:
            return None
        
        if self._monitoring_client is None:
            try:
                from google.cloud import monitoring_v3
                from backend.gcp.auth import get_gcp_credentials
                
                credentials, _ = get_gcp_credentials()
                self._monitoring_client = monitoring_v3.MetricServiceClient(credentials=credentials)
                logger.debug("Cloud Monitoring client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Cloud Monitoring client: {e}", exc_info=True)
                return None
        
        return self._monitoring_client
    
    async def get_all_resources(self) -> List[Dict[str, Any]]:
        """
        Get all GCP resources (Compute Engine, Cloud SQL, Memorystore).
        
        Returns:
            List of resource dictionaries with normalized format
        """
        if not settings.GCP_ENABLED:
            logger.debug("GCP is disabled, returning empty resource list")
            return []
        
        resources = []
        
        try:
            # Get Compute Engine instances (non-blocking - continue even if fails)
            try:
                compute_resources = await self._get_compute_instances()
                resources.extend(compute_resources)
                logger.debug(f"Retrieved {len(compute_resources)} Compute Engine instances")
            except Exception as e:
                logger.warning(f"Failed to get Compute Engine instances: {e}")
            
            # Get Cloud SQL instances (non-blocking - continue even if fails)
            try:
                sql_resources = await self._get_sql_instances()
                resources.extend(sql_resources)
                if sql_resources:
                    logger.info(f"Retrieved {len(sql_resources)} Cloud SQL instances: {[r['name'] for r in sql_resources]}")
                else:
                    # Check if SQL client is available (might be auth issue)
                    sql_client = self._get_sql_client()
                    if sql_client is None:
                        logger.debug("Cloud SQL client not available (likely authentication issue). Run './fix_gcp_auth.sh' to fix.")
                    else:
                        logger.debug("No Cloud SQL instances found in project (or API call returned empty)")
            except Exception as e:
                logger.warning(f"Failed to get Cloud SQL instances: {e}")
            
            # Get Memorystore (Redis) instances (non-blocking - continue even if fails)
            try:
                redis_resources = await self._get_redis_instances()
                resources.extend(redis_resources)
                logger.debug(f"Retrieved {len(redis_resources)} Memorystore instances")
            except Exception as e:
                logger.warning(f"Failed to get Memorystore instances: {e}")
            
            logger.info(f"Retrieved {len(resources)} GCP resources")
        except Exception as e:
            logger.error(f"Error getting GCP resources: {e}", exc_info=True)
        
        return resources
    
    async def _get_compute_instances(self) -> List[Dict[str, Any]]:
        """Get Compute Engine VM instances."""
        resources = []
        
        try:
            client = self._get_compute_client()
            if not client:
                return resources
            
            # List instances in the configured zone
            request = {
                "project": self.project_id,
                "zone": settings.GCP_ZONE,
            }
            
            instances = client.list(request=request)
            
            for instance in instances:
                # Get instance status and metrics
                status = instance.status  # RUNNING, STOPPING, TERMINATED, etc.
                
                # Normalize status
                normalized_status = "HEALTHY"
                if status == "TERMINATED" or status == "STOPPING":
                    normalized_status = "FAILED"
                elif status == "STAGING" or status == "PROVISIONING":
                    normalized_status = "DEGRADED"
                
                # Get metrics (CPU, memory) from Cloud Monitoring
                metrics = await self._get_compute_metrics(instance.name)
                
                resource = {
                    "id": f"gcp-compute-{instance.name}",
                    "name": instance.name,
                    "type": "gcp-compute",
                    "status": normalized_status,
                    "image": instance.machine_type.split('/')[-1] if instance.machine_type else "unknown",
                    "metrics": metrics,
                    "last_updated": datetime.utcnow().isoformat(),
                    "created_at": instance.creation_timestamp if hasattr(instance, 'creation_timestamp') else "",
                    "ports": "",
                    "gcp_zone": settings.GCP_ZONE,
                    "gcp_project": self.project_id,
                }
                resources.append(resource)
                
        except Exception as e:
            logger.error(f"Error getting Compute Engine instances: {e}", exc_info=True)
        
        return resources
    
    async def _get_sql_instances(self) -> List[Dict[str, Any]]:
        """Get Cloud SQL instances."""
        resources = []
        
        try:
            client = self._get_sql_client()
            if not client:
                return resources
            
            # List SQL instances
            request = client.instances().list(project=self.project_id)
            try:
                # Use asyncio.to_thread to avoid blocking and handle errors gracefully
                response = await asyncio.to_thread(request.execute)
            except Exception as auth_error:
                # Check if it's an auth error (RefreshError with id_token instead of access_token)
                error_type = type(auth_error).__name__
                error_str = str(auth_error).lower()
                if 'RefreshError' in error_type or 'access token' in error_str or 'id_token' in error_str:
                    # Service account failed, try ADC as fallback
                    logger.info("Cloud SQL API call failed with service account, trying Application Default Credentials...")
                    try:
                        from google.auth import default
                        from googleapiclient.discovery import build
                        adc_credentials, _ = default(scopes=[
                            'https://www.googleapis.com/auth/cloud-platform',
                            'https://www.googleapis.com/auth/sqlservice.admin',
                        ])
                        adc_client = build('sqladmin', 'v1', credentials=adc_credentials)
                        adc_request = adc_client.instances().list(project=self.project_id)
                        response = await asyncio.to_thread(adc_request.execute)
                        logger.info("Cloud SQL API call succeeded with Application Default Credentials")
                        # Update the client for future use
                        self._sql_client = adc_client
                    except Exception as adc_error:
                        logger.debug(f"ADC also failed for Cloud SQL API call: {adc_error}")
                        return resources  # Return empty list instead of failing
                else:
                    raise  # Re-raise if it's a different error
            
            instances = response.get('items', [])
            
            for instance in instances:
                # Get instance status
                state = instance.get('state', 'UNKNOWN')
                
                # Normalize status
                normalized_status = "HEALTHY"
                if state == "FAILED" or state == "MAINTENANCE":
                    normalized_status = "FAILED"
                elif state == "PENDING_CREATE" or state == "PENDING_UPDATE":
                    normalized_status = "DEGRADED"
                
                # Get metrics
                metrics = await self._get_sql_metrics(instance['name'])
                
                resource = {
                    "id": f"gcp-sql-{instance['name']}",
                    "name": instance['name'],
                    "type": "gcp-sql",
                    "status": normalized_status,
                    "image": instance.get('databaseVersion', 'unknown'),
                    "metrics": metrics,
                    "last_updated": datetime.utcnow().isoformat(),
                    "created_at": instance.get('createTime', ''),
                    "ports": "",
                    "gcp_region": instance.get('region', ''),
                    "gcp_project": self.project_id,
                }
                resources.append(resource)
                
        except Exception as e:
            logger.error(f"Error getting Cloud SQL instances: {e}", exc_info=True)
        
        return resources
    
    async def _get_redis_instances(self) -> List[Dict[str, Any]]:
        """Get Memorystore (Redis) instances."""
        resources = []
        
        try:
            client = self._get_redis_client()
            if not client:
                return resources
            
            # List Redis instances
            parent = f"projects/{self.project_id}/locations/{settings.GCP_REGION}"
            instances = client.list_instances(request={"parent": parent})
            
            for instance in instances:
                # Get instance status
                state = instance.state
                
                # Get state name and value
                state_value = state.value if hasattr(state, 'value') else int(state) if isinstance(state, (int, str)) and str(state).isdigit() else None
                state_name = state.name if hasattr(state, 'name') else None
                state_str = str(state)
                
                # Preserve actual state names instead of normalizing to DEGRADED
                # State enum values: READY=0, CREATING=1, UPDATING=3, DELETING=4, REPAIRING=5, FAILED=6
                if state_name:
                    # Use the actual state name (UPDATING, CREATING, READY, etc.)
                    normalized_status = state_name
                elif state_value is not None:
                    # Map numeric values to state names if name not available
                    state_map = {
                        0: "READY",
                        1: "CREATING",
                        3: "UPDATING",
                        4: "DELETING",
                        5: "REPAIRING",
                        6: "FAILED"
                    }
                    normalized_status = state_map.get(state_value, f"UNKNOWN_{state_value}")
                else:
                    # Fallback to string representation
                    normalized_status = state_str.upper() if state_str else "UNKNOWN"
                
                # Get metrics (include memory_size_gb from instance)
                metrics = await self._get_redis_metrics(instance.name, instance.memory_size_gb)
                
                resource = {
                    "id": f"gcp-redis-{instance.name.split('/')[-1]}",
                    "name": instance.name.split('/')[-1],
                    "type": "gcp-redis",
                    "status": normalized_status,
                    "image": f"Redis {instance.redis_version}",
                    "metrics": metrics,
                    "last_updated": datetime.utcnow().isoformat(),
                    "created_at": instance.create_time.isoformat() if hasattr(instance, 'create_time') else "",
                    "ports": "",
                    "gcp_region": settings.GCP_REGION,
                    "gcp_project": self.project_id,
                }
                resources.append(resource)
                
        except Exception as e:
            logger.error(f"Error getting Memorystore instances: {e}", exc_info=True)
        
        return resources
    
    async def _get_compute_metrics(self, instance_name: str) -> Dict[str, Any]:
        """Get Compute Engine instance metrics from Cloud Monitoring."""
        metrics = {
            "cpu_usage_percent": 0.0,
            "memory_usage_percent": 0.0,
            "disk_usage_percent": 0.0,
        }
        
        try:
            client = self._get_monitoring_client()
            if not client:
                return metrics
            
            # TODO: Implement Cloud Monitoring API calls to get CPU, memory, disk metrics
            # This requires querying time series data from Cloud Monitoring
            
        except Exception as e:
            logger.debug(f"Error getting Compute Engine metrics for {instance_name}: {e}")
        
        return metrics
    
    async def _get_sql_metrics(self, instance_name: str) -> Dict[str, Any]:
        """Get Cloud SQL instance metrics."""
        metrics = {
            "cpu_usage_percent": 0.0,
            "memory_usage_percent": 0.0,
            "storage_usage_percent": 0.0,
            "active_connections": 0,
            "max_connections": 0,
        }
        
        try:
            # TODO: Implement Cloud Monitoring API calls to get SQL metrics
            pass
        except Exception as e:
            logger.debug(f"Error getting Cloud SQL metrics for {instance_name}: {e}")
        
        return metrics
    
    async def _get_redis_metrics(self, instance_name: str, memory_size_gb: float = 0.0) -> Dict[str, Any]:
        """Get Memorystore (Redis) instance metrics."""
        # Convert GB to bytes for frontend compatibility
        # Frontend expects redis_max_memory_bytes and redis_used_memory_bytes
        memory_size_bytes = memory_size_gb * 1024 * 1024 * 1024  # GB to bytes
        memory_size_mb = memory_size_gb * 1024
        
        metrics = {
            "memory_usage_percent": 0.0,
            "cpu_usage_percent": 0.0,
            "hit_rate": 0.0,
            # Frontend expects these field names (from ResourceDashboard.js)
            "redis_max_memory_bytes": memory_size_bytes,
            "redis_used_memory_bytes": 0,  # Will be populated from Cloud Monitoring if available
            "redis_memory_usage_percent": 0.0,  # Will be populated from Cloud Monitoring if available
            # Also include for backward compatibility
            "memory_size_gb": memory_size_gb,
            "memory_size_mb": memory_size_mb,
            "memory_used_mb": 0.0,
        }
        
        try:
            # TODO: Implement Cloud Monitoring API calls to get actual Redis usage metrics
            # For now, we at least include the memory capacity
            pass
        except Exception as e:
            logger.debug(f"Error getting Memorystore metrics for {instance_name}: {e}")
        
        return metrics

