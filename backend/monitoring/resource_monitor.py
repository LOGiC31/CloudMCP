"""Resource monitoring for infrastructure components."""
import docker
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.config import settings
from backend.utils.logger import get_logger
from backend.utils.docker_helper import get_containers_via_cli, get_container_stats_via_cli

logger = get_logger(__name__)


class ResourceMonitor:
    """Monitor infrastructure resources."""
    
    def __init__(self):
        """Initialize resource monitor."""
        self.docker_client = None
        self._init_docker_client()
    
    def _init_docker_client(self):
        """Initialize Docker client with error handling."""
        try:
            import os
            # Remove any bad environment variables that might interfere
            old_docker_host = os.environ.pop("DOCKER_HOST", None)
            old_docker_context = os.environ.pop("DOCKER_CONTEXT", None)
            
            try:
                # Try Colima socket first (most reliable)
                colima_socket = os.path.expanduser("~/.colima/default/docker.sock")
                if os.path.exists(colima_socket):
                    # Use APIClient directly to avoid config file issues
                    from docker import APIClient
                    api_client = APIClient(base_url=f"unix://{colima_socket}", version='auto', timeout=5)
                    # Wrap in DockerClient for easier use
                    self.docker_client = docker.DockerClient(base_url=f"unix://{colima_socket}")
                else:
                    # Try default Docker socket
                    default_socket = "/var/run/docker.sock"
                    if os.path.exists(default_socket):
                        self.docker_client = docker.DockerClient(base_url=f"unix://{default_socket}")
                    else:
                        # Last resort: from_env
                        self.docker_client = docker.from_env()
                
                # Test connection
                self.docker_client.ping()
            finally:
                # Restore environment variables if they were set
                if old_docker_host:
                    os.environ["DOCKER_HOST"] = old_docker_host
                if old_docker_context:
                    os.environ["DOCKER_CONTEXT"] = old_docker_context
        except docker.errors.DockerException as e:
            self.docker_client = None
            logger.warning(f"Docker not available: {e}. Resource monitoring will be limited.")
        except Exception as e:
            self.docker_client = None
            logger.warning(f"Failed to initialize Docker client: {e}. Resource monitoring will be limited.")
    
    async def get_resource_status(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific resource."""
        if not self.docker_client:
            # Fallback to CLI
            from backend.utils.docker_helper import get_containers_via_cli
            containers_data = get_containers_via_cli()
            for container_data in containers_data:
                if container_data.get("name", "").lstrip("/") == resource_id or container_data.get("id", "").startswith(resource_id):
                    return await self._get_container_status_from_data(container_data)
            return None
        
        try:
            container = self.docker_client.containers.get(resource_id)
            return await self._get_container_status(container)
        except docker.errors.NotFound:
            logger.warning(f"Resource not found: {resource_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting resource status: {e}", exc_info=True)
            return None
    
    async def get_all_resources(self, filter_excluded: bool = False) -> List[Dict[str, Any]]:
        """Get status of all resources.
        
        Args:
            filter_excluded: If True, exclude containers matching excluded patterns (default: False)
        """
        logger.debug(f"get_all_resources called (filter_excluded={filter_excluded})")
        resources = []
        
        # Containers to exclude (from other projects/tests)
        excluded_patterns = ["mcp-"]  # Exclude MCP test containers (if filtering enabled)
        
        if not self.docker_client:
            # Fallback to CLI
            logger.info("Docker client not available, using CLI fallback")
            containers_data = get_containers_via_cli()
            # Filter containers first
            filtered_containers_data = [
                container_data for container_data in containers_data
                if not (filter_excluded and any(pattern in container_data.get("name", "").lstrip("/") for pattern in excluded_patterns))
            ]
            
            # Process all containers in parallel
            status_tasks = [self._get_container_status_from_data(container_data) for container_data in filtered_containers_data]
            statuses = await asyncio.gather(*status_tasks, return_exceptions=True)
            
            # Collect successful statuses
            for status in statuses:
                if isinstance(status, dict) and status:
                    resources.append(status)
                elif isinstance(status, Exception):
                    logger.debug(f"Error getting container status: {status}")
            return resources
        
        try:
            logger.debug("Fetching containers from Docker client...")
            containers = self.docker_client.containers.list(all=True)
            logger.debug(f"Found {len(containers)} total containers")
            
            # Filter containers first
            filtered_containers = [
                container for container in containers
                if not (filter_excluded and any(pattern in container.name for pattern in excluded_patterns))
            ]
            logger.debug(f"Processing {len(filtered_containers)} containers after filtering")
            
            # Process all containers in parallel
            logger.debug("Starting parallel status checks...")
            status_tasks = [self._get_container_status(container) for container in filtered_containers]
            statuses = await asyncio.gather(*status_tasks, return_exceptions=True)
            
            # Collect successful statuses
            for i, status in enumerate(statuses):
                if isinstance(status, dict) and status:
                    resources.append(status)
                    logger.debug(f"Container {filtered_containers[i].name}: {status.get('status', 'UNKNOWN')}")
                elif isinstance(status, Exception):
                    logger.warning(f"Error getting status for container {filtered_containers[i].name}: {status}", exc_info=isinstance(status, Exception))
            
            logger.info(f"Successfully retrieved status for {len(resources)}/{len(filtered_containers)} containers")
        except Exception as e:
            logger.error(f"Error getting all resources: {e}", exc_info=True)
            # Fallback to CLI
            logger.info("Falling back to Docker CLI")
            containers_data = get_containers_via_cli()
            # Filter containers first
            filtered_containers_data = [
                container_data for container_data in containers_data
                if not (filter_excluded and any(pattern in container_data.get("name", "").lstrip("/") for pattern in excluded_patterns))
            ]
            
            # Process all containers in parallel
            status_tasks = [self._get_container_status_from_data(container_data) for container_data in filtered_containers_data]
            statuses = await asyncio.gather(*status_tasks, return_exceptions=True)
            
            # Collect successful statuses
            for status in statuses:
                if isinstance(status, dict) and status:
                    resources.append(status)
                elif isinstance(status, Exception):
                    logger.debug(f"Error getting container status: {status}")
        
        return resources
    
    async def _get_container_status(self, container) -> Dict[str, Any]:
        """Get status of a Docker container."""
        try:
            # Run reload in thread pool to avoid blocking
            await asyncio.to_thread(container.reload)
            
            # Determine resource type
            resource_type = "docker"
            image_name = container.image.tags[0] if container.image.tags else ""
            if "postgres" in image_name.lower():
                resource_type = "postgres"
            elif "redis" in image_name.lower():
                resource_type = "redis"
            elif "nginx" in image_name.lower() or "nginx" in container.name.lower():
                resource_type = "nginx"
            elif "sample-app" in image_name.lower() or "app" in container.name.lower():
                resource_type = "application"
            
            # Determine status based on container and application metrics
            status = "UNKNOWN"
            if container.status == "running":
                status = "HEALTHY"
            elif container.status == "exited":
                status = "FAILED"
            elif container.status == "restarting":
                status = "DEGRADED"
            else:
                status = container.status.upper()
            
            # Get metrics (run stats and app-specific checks in parallel)
            metrics = {}
            try:
                # Run stats and app-specific checks in parallel
                stats_task = asyncio.to_thread(container.stats, stream=False)
                app_check_task = None
                
                if resource_type == "redis":
                    app_check_task = self._check_redis_memory(container.name)
                elif resource_type == "postgres":
                    app_check_task = self._check_postgres_connections(container.name)
                elif resource_type == "nginx":
                    app_check_task = self._check_nginx_connections(container.name)
                
                # Wait for stats (required) and app check (optional) in parallel
                if app_check_task:
                    stats, app_status = await asyncio.gather(stats_task, app_check_task, return_exceptions=True)
                else:
                    stats = await stats_task
                    app_status = None
                
                if isinstance(stats, Exception):
                    raise stats
                
                cpu_percent = self._calculate_cpu_percent(stats)
                memory_stats = stats.get('memory_stats', {})
                mem_usage = memory_stats.get('usage', 0)
                mem_limit = memory_stats.get('limit', 0)
                mem_percent = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0
                
                metrics = {
                    "cpu_usage_percent": cpu_percent,
                    "memory_usage_bytes": mem_usage,
                    "memory_limit_bytes": mem_limit,
                    "memory_usage_percent": mem_percent
                }
                
                # Process app-specific status
                if app_status and not isinstance(app_status, Exception):
                    if resource_type == "redis":
                        metrics.update(app_status)
                        if app_status.get("redis_memory_usage_percent", 0) > 95:
                            status = "DEGRADED"
                    elif resource_type == "postgres":
                        metrics.update(app_status)
                        max_conn = app_status.get("max_connections", 100)
                        total_conn = app_status.get("total_connections", 0)
                        if max_conn > 0 and (total_conn / max_conn) > 0.8:
                            status = "DEGRADED"
                            logger.info(f"PostgreSQL connection overload detected: {total_conn}/{max_conn} ({total_conn/max_conn*100:.1f}%)")
                    elif resource_type == "nginx":
                        metrics.update(app_status)
                        active_conn = app_status.get("active_connections", 0)
                        worker_conn = app_status.get("worker_connections", 100)
                        if worker_conn > 0 and (active_conn / worker_conn) > 0.8:
                            status = "DEGRADED"
                            logger.info(f"Nginx connection overload detected: {active_conn}/{worker_conn} ({active_conn/worker_conn*100:.1f}%)")
                
                # Check container memory pressure
                if mem_percent > 90:
                    status = "DEGRADED"
                elif mem_percent > 95:
                    status = "FAILED"
                    
            except Exception as e:
                logger.debug(f"Could not get metrics for {container.name}: {e}")
            
            return {
                "id": container.id,
                "name": container.name,
                "type": resource_type,
                "status": status,
                "image": image_name,
                "metrics": metrics,
                "last_updated": datetime.utcnow().isoformat(),
                "created_at": container.attrs.get('Created', ''),
                "ports": container.attrs.get('NetworkSettings', {}).get('Ports', {})
            }
        except Exception as e:
            logger.error(f"Error getting container status: {e}", exc_info=True)
            return None
    
    async def _get_container_status_from_data(self, container_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get container status from CLI data."""
        try:
            name = container_data.get("name", "").lstrip("/")
            status_str = container_data.get("status", "")
            
            # Determine resource type
            resource_type = "docker"
            image_name = container_data.get("image", "")
            if "postgres" in image_name.lower():
                resource_type = "postgres"
            elif "redis" in image_name.lower():
                resource_type = "redis"
            elif "nginx" in image_name.lower() or "nginx" in name.lower():
                resource_type = "nginx"
            elif "sample-app" in image_name.lower() or "app" in name.lower():
                resource_type = "application"
            
            # Determine status based on container and application metrics
            status = "UNKNOWN"
            if "Up" in status_str:
                status = "HEALTHY"
            elif "Exited" in status_str:
                status = "FAILED"
            elif "Restarting" in status_str:
                status = "DEGRADED"
            else:
                status = status_str.split()[0].upper() if status_str else "UNKNOWN"
            
            # Get stats if available (run stats and app checks in parallel)
            metrics = {}
            stats = get_container_stats_via_cli(name)
            if stats:
                try:
                    cpu_percent = float(stats.get("CPUPerc", "0%").rstrip("%"))
                    mem_usage = stats.get("MemUsage", "0B / 0B").split(" / ")
                    mem_used = self._parse_size(mem_usage[0]) if len(mem_usage) > 0 else 0
                    mem_limit = self._parse_size(mem_usage[1]) if len(mem_usage) > 1 else 0
                    mem_percent = (mem_used / mem_limit * 100) if mem_limit > 0 else 0
                    
                    metrics = {
                        "cpu_usage_percent": cpu_percent,
                        "memory_usage_bytes": mem_used,
                        "memory_limit_bytes": mem_limit,
                        "memory_usage_percent": mem_percent
                    }
                    
                    # Run app-specific checks in parallel with stats processing
                    app_check_task = None
                    if resource_type == "redis":
                        app_check_task = self._check_redis_memory(name)
                    elif resource_type == "postgres":
                        app_check_task = self._check_postgres_connections(name)
                    elif resource_type == "nginx":
                        app_check_task = self._check_nginx_connections(name)
                    
                    # Wait for app check if needed
                    app_status = None
                    if app_check_task:
                        app_status = await app_check_task
                    
                    # Process app-specific status
                    if app_status:
                        if resource_type == "redis":
                            metrics.update(app_status)
                            if app_status.get("redis_memory_usage_percent", 0) > 95:
                                status = "DEGRADED"
                        elif resource_type == "postgres":
                            metrics.update(app_status)
                            max_conn = app_status.get("max_connections", 100)
                            total_conn = app_status.get("total_connections", 0)
                            if max_conn > 0 and (total_conn / max_conn) > 0.8:
                                status = "DEGRADED"
                        elif resource_type == "nginx":
                            metrics.update(app_status)
                            active_conn = app_status.get("active_connections", 0)
                            worker_conn = app_status.get("worker_connections", 100)
                            if worker_conn > 0 and (active_conn / worker_conn) > 0.8:
                                status = "DEGRADED"
                                logger.info(f"Nginx connection overload detected: {active_conn}/{worker_conn} ({active_conn/worker_conn*100:.1f}%)")
                    
                    # Check container memory pressure
                    if mem_percent > 90:
                        status = "DEGRADED"
                    elif mem_percent > 95:
                        status = "FAILED"
                        
                except Exception as e:
                    logger.debug(f"Error getting metrics for {name}: {e}")
            
            return {
                "id": container_data.get("id", ""),
                "name": name,
                "type": resource_type,
                "status": status,
                "image": image_name,
                "metrics": metrics,
                "last_updated": datetime.utcnow().isoformat(),
                "created_at": "",
                "ports": container_data.get("ports", "")
            }
        except Exception as e:
            logger.error(f"Error getting container status from data: {e}", exc_info=True)
            return None
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '256MiB' to bytes."""
        try:
            size_str = size_str.strip().upper()
            if size_str.endswith("B"):
                size_str = size_str[:-1]
            
            multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
            for suffix, multiplier in multipliers.items():
                if size_str.endswith(suffix):
                    return int(float(size_str[:-1]) * multiplier)
            
            return int(float(size_str))
        except Exception:
            return 0
    
    async def _check_redis_memory(self, container_name: str) -> Optional[Dict[str, Any]]:
        """Check Redis memory usage using async subprocess."""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "exec", container_name, "redis-cli", "INFO", "memory",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return None
            
            if process.returncode == 0:
                output = stdout.decode('utf-8')
                info = {}
                for line in output.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip()] = value.strip()
                
                used_memory = int(info.get("used_memory", 0))
                maxmemory = int(info.get("maxmemory", 0))
                
                if maxmemory > 0:
                    return {
                        "redis_used_memory_bytes": used_memory,
                        "redis_max_memory_bytes": maxmemory,
                        "redis_memory_usage_percent": (used_memory / maxmemory) * 100
                    }
        except Exception as e:
            logger.debug(f"Error checking Redis memory: {e}")
        return None
    
    async def _check_postgres_connections(self, container_name: str) -> Optional[Dict[str, Any]]:
        """Check PostgreSQL connection count using async subprocess and parallel queries."""
        try:
            # Run all queries in parallel
            total_query = asyncio.create_subprocess_exec(
                "docker", "exec", container_name, "psql", "-U", "postgres", "-d", "sample_app",
                "-t", "-c", "SELECT count(*) FILTER (WHERE state = 'active') AS active_connections, "
                            "count(*) FILTER (WHERE state = 'idle') AS idle_connections, "
                            "count(*) AS total_connections, "
                            "current_setting('max_connections')::int AS max_connections "
                            "FROM pg_stat_activity WHERE pid != pg_backend_pid();",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            process = await total_query
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return None
            
            if process.returncode == 0:
                output = stdout.decode('utf-8').strip()
                # Parse the result: active|idle|total|max
                parts = output.split('|')
                if len(parts) >= 4:
                    active_connections = int(parts[0].strip() or 0)
                    idle_connections = int(parts[1].strip() or 0)
                    total_connections = int(parts[2].strip() or 0)
                    max_connections = int(parts[3].strip() or 100)
                else:
                    # Fallback parsing
                    active_connections = int(output.strip() or 0)
                    total_connections = active_connections
                    idle_connections = 0
                    max_connections = 100
                
                return {
                    "active_connections": active_connections,
                    "idle_connections": idle_connections,
                    "total_connections": total_connections,
                    "max_connections": max_connections,
                    "connection_usage_percent": (total_connections / max_connections) * 100 if max_connections > 0 else 0
                }
        except Exception as e:
            logger.debug(f"Error checking PostgreSQL connections: {e}")
        return None
    
    async def _check_nginx_connections(self, container_name: str) -> Optional[Dict[str, Any]]:
        """Check Nginx active connections and worker_connections limit."""
        try:
            # Try multiple methods to get connection count
            # Method 1: Try netstat
            process = await asyncio.create_subprocess_exec(
                "docker", "exec", container_name, "sh", "-c",
                "netstat -an 2>/dev/null | grep :80 | grep ESTABLISHED | wc -l || echo 0",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                stdout = b"0"
            
            active_connections = 0
            if process.returncode == 0:
                try:
                    active_connections = int(stdout.decode('utf-8').strip() or 0)
                except ValueError:
                    active_connections = 0
            
            # If netstat didn't work or returned 0, try ss (more modern, more reliable)
            if active_connections == 0:
                try:
                    ss_process = await asyncio.create_subprocess_exec(
                        "docker", "exec", container_name, "sh", "-c",
                        "ss -tn state established '( dport = :80 )' 2>/dev/null | tail -n +2 | wc -l || ss -tn 2>/dev/null | grep :80 | grep ESTAB | wc -l || echo 0",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    ss_stdout, _ = await asyncio.wait_for(ss_process.communicate(), timeout=3)
                    if ss_process.returncode == 0:
                        try:
                            ss_count = int(ss_stdout.decode('utf-8').strip() or 0)
                            if ss_count > 0:
                                active_connections = ss_count
                        except ValueError:
                            pass
                except Exception:
                    pass
            
            # Also try checking from host side (connections to port 8080 map to nginx:80)
            # This is a fallback if container-side detection doesn't work
            if active_connections == 0:
                try:
                    host_process = await asyncio.create_subprocess_exec(
                        "sh", "-c",
                        "netstat -an 2>/dev/null | grep :8080 | grep ESTABLISHED | wc -l || ss -tn 2>/dev/null | grep :8080 | grep ESTAB | wc -l || echo 0",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    host_stdout, _ = await asyncio.wait_for(host_process.communicate(), timeout=2)
                    if host_process.returncode == 0:
                        try:
                            host_count = int(host_stdout.decode('utf-8').strip() or 0)
                            # Use host count as approximation (may include other connections, but better than 0)
                            if host_count > active_connections:
                                active_connections = host_count
                        except ValueError:
                            pass
                except Exception:
                    pass
            
            # Get worker_connections from config (default 100)
            # We'll read from the config file or use default
            worker_connections = 100  # Default from nginx.conf
            try:
                config_process = await asyncio.create_subprocess_exec(
                    "docker", "exec", container_name, "sh", "-c",
                    "grep worker_connections /etc/nginx/nginx.conf | awk '{print $2}' | sed 's/;//'",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                config_stdout, _ = await asyncio.wait_for(config_process.communicate(), timeout=2)
                if config_process.returncode == 0:
                    try:
                        worker_connections = int(config_stdout.decode('utf-8').strip() or 100)
                    except ValueError:
                        worker_connections = 100
            except Exception:
                pass  # Use default
            
            connection_usage_percent = (active_connections / worker_connections) * 100 if worker_connections > 0 else 0
            
            return {
                "active_connections": active_connections,
                "worker_connections": worker_connections,
                "connection_usage_percent": round(connection_usage_percent, 2)
            }
        except Exception as e:
            logger.debug(f"Error checking Nginx connections: {e}")
        return None
    
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
    
    async def get_metrics(
        self,
        resource_id: str,
        time_range: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get metrics for a resource."""
        status = await self.get_resource_status(resource_id)
        if not status:
            return {}
        
        return {
            "resource_id": resource_id,
            "metrics": status.get("metrics", {}),
            "timestamp": status.get("last_updated")
        }

