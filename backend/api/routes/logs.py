"""Log management API routes."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from backend.monitoring.log_accumulator import LogAccumulator

router = APIRouter(prefix="/logs", tags=["logs"])
log_accumulator = LogAccumulator()


@router.get("", response_model=List[Dict[str, Any]])
async def get_logs(
    level: Optional[str] = Query(None, description="Filter by log level"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    limit: int = Query(100, description="Maximum number of logs to return")
):
    """Get logs with optional filters."""
    try:
        # For now, get error logs and filter
        logs = await log_accumulator.get_error_logs()
        
        if level:
            logs = [log for log in logs if log.get("level") == level.upper()]
        
        if resource_id:
            logs = [log for log in logs if log.get("resource_id") == resource_id]
        
        return logs[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors", response_model=List[Dict[str, Any]])
async def get_error_logs(
    limit: int = Query(100, description="Maximum number of logs to return")
):
    """Get error logs only."""
    try:
        logs = await log_accumulator.get_error_logs()
        return logs[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

