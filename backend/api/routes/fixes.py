"""Fix management API routes."""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from backend.core.orchestrator import MCPOrchestrator
from backend.evaluation.store import EvaluationStore
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/fixes", tags=["fixes"])
orchestrator = MCPOrchestrator()
evaluation_store = EvaluationStore()


class FixTriggerRequest(BaseModel):
    """Request model for triggering a fix."""
    resource_ids: Optional[List[str]] = None
    time_range: Optional[Dict[str, str]] = None


@router.post("/trigger", response_model=Dict[str, Any])
async def trigger_fix(request: FixTriggerRequest):
    """User-triggered fix."""
    try:
        logger.info(f"Fix trigger requested - resource_ids: {request.resource_ids}, time_range: {request.time_range}")
        failure_context = {
            "resource_ids": request.resource_ids,
            "time_range": request.time_range
        }
        logger.debug(f"Calling orchestrator.trigger_fix with context: {failure_context}")
        result = await orchestrator.trigger_fix(failure_context)
        logger.info(f"Fix triggered successfully - fix_id: {result.get('id', 'unknown')}, status: {result.get('execution_status', 'unknown')}")
        return result
    except Exception as e:
        logger.error(f"Error triggering fix: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Dict[str, Any]])
async def get_fixes(limit: int = 100):
    """Get all fix attempts."""
    try:
        evaluations = await evaluation_store.get_fix_evaluations(limit=limit)
        return evaluations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{fix_id}", response_model=Dict[str, Any])
async def get_fix(fix_id: str):
    """Get specific fix result."""
    try:
        evaluation = await evaluation_store.get_fix_evaluation(fix_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail="Fix not found")
        return evaluation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluations", response_model=List[Dict[str, Any]])
async def get_evaluations(limit: int = 100):
    """Get evaluation data."""
    try:
        evaluations = await evaluation_store.get_fix_evaluations(limit=limit)
        return evaluations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("", response_model=Dict[str, Any])
async def delete_all_fixes():
    """Delete all fix evaluations."""
    try:
        count = await evaluation_store.delete_all_fixes()
        return {"message": f"Deleted {count} fix evaluations", "deleted_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{fix_id}", response_model=Dict[str, Any])
async def delete_fix(fix_id: str):
    """Delete a specific fix evaluation."""
    try:
        deleted = await evaluation_store.delete_fix(fix_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Fix not found")
        return {"message": f"Deleted fix evaluation: {fix_id}", "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

