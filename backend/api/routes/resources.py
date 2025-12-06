"""Resource management API routes."""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from backend.monitoring.resource_monitor import ResourceMonitor
from backend.mcp.tools.redis_tools import RedisFlushTool
from backend.utils.logger import get_logger
import subprocess
import asyncio

logger = get_logger(__name__)
router = APIRouter(prefix="/resources", tags=["resources"])

# Lazy initialization - only create when needed
_resource_monitor = None

def get_resource_monitor():
    """Get or create ResourceMonitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


@router.get("", response_model=List[Dict[str, Any]])
async def get_all_resources(filter_excluded: bool = True):
    """Get all resources and their status."""
    try:
        logger.info(f"Getting all resources (filter_excluded={filter_excluded})")
        resource_monitor = get_resource_monitor()
        resources = await resource_monitor.get_all_resources(filter_excluded=filter_excluded)
        logger.info(f"Retrieved {len(resources)} resources: {[r['name'] for r in resources]}")
        return resources
    except Exception as e:
        logger.error(f"Error getting all resources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{resource_id}", response_model=Dict[str, Any])
async def get_resource(resource_id: str):
    """Get specific resource status."""
    try:
        resource_monitor = get_resource_monitor()
        resource = await resource_monitor.get_resource_status(resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        return resource
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{resource_id}/metrics", response_model=Dict[str, Any])
async def get_resource_metrics(resource_id: str):
    """Get resource metrics."""
    try:
        resource_monitor = get_resource_monitor()
        metrics = await resource_monitor.get_metrics(resource_id)
        if not metrics:
            raise HTTPException(status_code=404, detail="Resource not found")
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/redis/reset", response_model=Dict[str, Any])
async def reset_redis():
    """Reset Redis by flushing all data and resetting maxmemory to 256MB."""
    try:
        logger.info("Starting Redis reset operation")
        
        # Flush all Redis data
        logger.debug("Flushing Redis data...")
        flush_tool = RedisFlushTool()
        flush_result = await flush_tool.execute({"db": -1})  # Flush all databases
        
        if not flush_result.success:
            logger.error(f"Failed to flush Redis: {flush_result.message}")
            raise HTTPException(status_code=500, detail=f"Failed to flush Redis: {flush_result.message}")
        
        logger.info("Redis data flushed successfully")
        
        # Reset maxmemory to 256MB (docker-compose default)
        logger.debug("Resetting Redis maxmemory to 256MB...")
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "exec", "redis", "redis-cli", "CONFIG", "SET", "maxmemory", "256mb",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
            
            if process.returncode == 0:
                logger.debug("Maxmemory set to 256MB")
                # Also set the policy
                process2 = await asyncio.create_subprocess_exec(
                    "docker", "exec", "redis", "redis-cli", "CONFIG", "SET", "maxmemory-policy", "allkeys-lru",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(process2.communicate(), timeout=5)
                logger.debug("Maxmemory policy set to allkeys-lru")
            else:
                logger.warning(f"Failed to set maxmemory via CONFIG SET: {stderr.decode()}")
        except Exception as e:
            # Config set might fail if maxmemory is set in redis.conf, but flush should still work
            logger.warning(f"Could not set maxmemory via CONFIG SET (may be set in redis.conf): {e}")
        
        logger.info("Redis reset completed successfully")
        return {
            "message": "Redis reset successfully - all data flushed and maxmemory reset to 256MB",
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting Redis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset Redis: {str(e)}")


@router.post("/postgres/reset", response_model=Dict[str, Any])
async def reset_postgres():
    """Reset PostgreSQL by killing all active connections."""
    try:
        logger.info("Starting PostgreSQL reset operation")
        logger.debug("Terminating all active connections...")
        
        # Kill all connections except our own
        process = await asyncio.create_subprocess_exec(
            "docker", "exec", "postgres", "psql", "-U", "postgres", "-d", "sample_app",
            "-c", "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid != pg_backend_pid() AND datname = 'sample_app';",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        
        if process.returncode != 0:
            logger.error(f"Failed to reset PostgreSQL: {stderr.decode()}")
            raise HTTPException(status_code=500, detail=f"Failed to reset PostgreSQL: {stderr.decode()}")
        
        logger.info(f"PostgreSQL reset completed. Output: {stdout.decode()}")
        return {
            "message": "PostgreSQL reset successfully - all active connections terminated",
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting PostgreSQL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset PostgreSQL: {str(e)}")

