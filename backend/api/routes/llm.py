"""LLM interaction API routes."""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from backend.core.llm_client import LLMClient

router = APIRouter(prefix="/llm", tags=["llm"])
llm_client = LLMClient()


@router.get("/interactions", response_model=List[Dict[str, Any]])
async def get_interactions(limit: int = 50):
    """Get all LLM interactions."""
    try:
        interactions = llm_client.get_interaction_history(limit=limit)
        return interactions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interactions/{interaction_id}", response_model=Dict[str, Any])
async def get_interaction(interaction_id: str):
    """Get specific LLM interaction."""
    try:
        interaction = llm_client.get_interaction(interaction_id)
        if not interaction:
            raise HTTPException(status_code=404, detail="Interaction not found")
        return interaction
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

