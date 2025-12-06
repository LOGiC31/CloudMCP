"""Evaluation data storage."""
import json
import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EvaluationStore:
    """Store evaluation data for fixes."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize evaluation store."""
        self.db_path = db_path or settings.DATABASE_URL.replace("sqlite:///", "")
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fix_evaluations (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                root_cause TEXT,
                fix_applied TEXT,
                tools_used TEXT,
                before_metrics TEXT,
                after_metrics TEXT,
                success INTEGER,
                llm_interaction_id TEXT,
                execution_status TEXT,
                fix_plan TEXT,
                tool_results TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Initialized evaluation database: {self.db_path}")
    
    async def store_fix_evaluation(self, fix_result: Dict[str, Any]):
        """Store a fix evaluation."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        fix_plan = fix_result.get("fix_plan", {})
        tools_used = [step.get("tool_name") for step in fix_plan.get("steps", [])]
        
        cursor.execute("""
            INSERT OR REPLACE INTO fix_evaluations (
                id, timestamp, root_cause, fix_applied, tools_used,
                before_metrics, after_metrics, success, llm_interaction_id,
                execution_status, fix_plan, tool_results
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fix_result["id"],
            fix_result["timestamp"],
            fix_plan.get("root_cause", ""),
            json.dumps(fix_plan.get("steps", [])),
            json.dumps(tools_used),
            json.dumps(fix_result.get("before_metrics", {})),
            json.dumps(fix_result.get("after_metrics", {})),
            1 if fix_result.get("execution_status") == "SUCCESS" else 0,
            fix_result.get("interaction_id", ""),
            fix_result.get("execution_status", "UNKNOWN"),
            json.dumps(fix_plan),
            json.dumps(fix_result.get("tool_results", []))
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Stored fix evaluation: {fix_result['id']}")
    
    async def get_fix_evaluations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get fix evaluations."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM fix_evaluations
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        evaluations = []
        for row in rows:
            evaluations.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "root_cause": row["root_cause"],
                "fix_applied": json.loads(row["fix_applied"]),
                "tools_used": json.loads(row["tools_used"]),
                "before_metrics": json.loads(row["before_metrics"]),
                "after_metrics": json.loads(row["after_metrics"]),
                "success": bool(row["success"]),
                "llm_interaction_id": row["llm_interaction_id"],
                "execution_status": row["execution_status"],
                "fix_plan": json.loads(row["fix_plan"]),
                "tool_results": json.loads(row["tool_results"])
            })
        
        return evaluations
    
    async def get_fix_evaluation(self, fix_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific fix evaluation."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM fix_evaluations WHERE id = ?", (fix_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "root_cause": row["root_cause"],
            "fix_applied": json.loads(row["fix_applied"]),
            "tools_used": json.loads(row["tools_used"]),
            "before_metrics": json.loads(row["before_metrics"]),
            "after_metrics": json.loads(row["after_metrics"]),
            "success": bool(row["success"]),
            "llm_interaction_id": row["llm_interaction_id"],
            "execution_status": row["execution_status"],
            "fix_plan": json.loads(row["fix_plan"]),
            "tool_results": json.loads(row["tool_results"])
        }
    
    async def delete_all_fixes(self) -> int:
        """Delete all fix evaluations. Returns the number of deleted records."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM fix_evaluations")
        count = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM fix_evaluations")
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted {count} fix evaluations from database")
        return count
    
    async def delete_fix(self, fix_id: str) -> bool:
        """Delete a specific fix evaluation. Returns True if deleted, False if not found."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM fix_evaluations WHERE id = ?", (fix_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"Deleted fix evaluation: {fix_id}")
        return deleted

