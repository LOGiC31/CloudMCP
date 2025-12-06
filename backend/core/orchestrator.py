"""MCP Orchestrator - Core orchestration logic."""
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.core.llm_client import LLMClient
from backend.monitoring.log_accumulator import LogAccumulator
from backend.monitoring.resource_monitor import ResourceMonitor
from backend.mcp.tools.registry import tool_registry
from backend.evaluation.store import EvaluationStore
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MCPOrchestrator:
    """Main orchestrator for infrastructure fixes."""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize orchestrator."""
        self.llm_client = llm_client or LLMClient()
        self.log_accumulator = LogAccumulator()
        self.resource_monitor = ResourceMonitor()
        self.evaluation_store = EvaluationStore()
    
    async def trigger_fix(
        self,
        failure_context: Optional[Dict[str, Any]] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Trigger a fix workflow with retry mechanism.
        
        Args:
            failure_context: Optional context with resource_ids, time_range, etc.
            max_retries: Maximum number of retry attempts (default: 2, so 3 total attempts)
            
        Returns:
            Fix result with execution details including all attempts
        """
        fix_id = f"fix_{uuid.uuid4().hex[:8]}"
        logger.info(f"Starting fix workflow: {fix_id} (max retries: {max_retries})")
        
        all_attempts = []
        last_failure_info = None
        original_before_metrics = None
        
        try:
            # Step 1: Collect failure context (once, before retry loop)
            if not failure_context:
                failure_context = {}
            
            resource_ids = failure_context.get("resource_ids")
            time_range = failure_context.get("time_range")
            
            # Collect logs
            logger.debug(f"Collecting error logs (resource_ids={resource_ids}, time_range={time_range})")
            logs = await self.log_accumulator.get_error_logs(
                time_range=time_range,
                resource_ids=resource_ids
            )
            logger.info(f"Collected {len(logs)} error logs")
            
            # Get initial resource status
            logger.debug("Collecting resource status...")
            if resource_ids:
                logger.debug(f"Getting status for specific resources: {resource_ids}")
                resource_status = [
                    await self.resource_monitor.get_resource_status(rid)
                    for rid in resource_ids
                ]
                resource_status = [r for r in resource_status if r]
            else:
                logger.debug("Getting status for all resources")
                resource_status = await self.resource_monitor.get_all_resources(filter_excluded=False)
            
            logger.info(f"Found {len(resource_status)} resources: {[r['name'] for r in resource_status]}")
            degraded_resources = [r for r in resource_status if r.get('status') in ['DEGRADED', 'FAILED']]
            if degraded_resources:
                logger.warning(f"Found {len(degraded_resources)} degraded/failed resources: {[r['name'] for r in degraded_resources]}")
            
            # Get app config
            logger.debug("Getting application configuration...")
            app_config = await self.log_accumulator.get_application_config()
            
            # Get available tools
            logger.debug("Getting available MCP tools...")
            available_tools = tool_registry.get_tools_for_llm()
            logger.info(f"Found {len(available_tools)} available MCP tools")
            
            # Retry loop
            for attempt in range(max_retries + 1):  # 0, 1, 2 = 3 attempts total
                attempt_num = attempt + 1
                logger.info(f"Fix attempt {attempt_num}/{max_retries + 1}: {fix_id}")
                
                try:
                    # Step 2: Analyze and create fix plan
                    logger.info(f"Analyzing failure with {len(logs)} error logs...")
                    
                    # Add previous attempt feedback if retrying
                    analysis_context = {
                        "logs": logs,
                        "app_config": app_config,
                        "available_tools": available_tools,
                        "resource_status": resource_status
                    }
                    
                    if attempt > 0 and last_failure_info:
                        analysis_context["previous_attempt"] = {
                            "attempt_number": attempt,
                            "tools_used": last_failure_info.get("tools_used", []),
                            "result": last_failure_info.get("result", {}),
                            "failed_resources": last_failure_info.get("failed_resources", []),
                            "message": f"Previous attempt {attempt} did not resolve the issue. Please try a different approach."
                        }
                        logger.info(f"Retry attempt {attempt_num}: Previous attempt failed. Trying different approach...")
                    
                    analysis_result = await self.llm_client.analyze_and_plan(**analysis_context)
                    
                    fix_plan = analysis_result["fix_plan"]
                    interaction = analysis_result.get("interaction", {})
                    
                    logger.info(f"Fix plan created: {fix_plan.get('root_cause', 'Unknown')}")
                    
                    # Step 3: Execute fix plan
                    before_metrics = await self._capture_metrics(resource_status)
                    if original_before_metrics is None:
                        original_before_metrics = before_metrics
                    
                    execution_results = []
                    for step in fix_plan.get("steps", []):
                        tool_name = step.get("tool_name")
                        parameters = step.get("parameters", {})
                        
                        logger.info(f"Executing tool: {tool_name} with params: {parameters}")
                        result = await tool_registry.execute_tool(tool_name, parameters)
                        execution_results.append({
                            "step": step,
                            "result": result
                        })
                        
                        if not result.get("success"):
                            logger.warning(f"Tool {tool_name} failed: {result.get('message')}")
                    
                    # Step 4: Verify fix
                    await asyncio.sleep(2)  # Wait a bit for changes to take effect
                    updated_resource_status = await self.resource_monitor.get_all_resources(filter_excluded=False)
                    after_metrics = await self._capture_metrics(updated_resource_status)
                    
                    # Determine success - check if issues were actually resolved
                    tool_success = all(r.get("result", {}).get("success", False) for r in execution_results)
                    
                    # Check if resources are actually healthy now
                    issues_resolved = True
                    failed_resources = []
                    for resource_name, before_metric in original_before_metrics.items():
                        after_metric = after_metrics.get(resource_name, {})
                        before_status = before_metric.get("status", "UNKNOWN")
                        after_status = after_metric.get("status", "UNKNOWN")
                        
                        # If resource was unhealthy before, check if it's healthy now
                        if before_status in ["DEGRADED", "FAILED"]:
                            if after_status not in ["HEALTHY"]:
                                issues_resolved = False
                                failed_resources.append({
                                    "resource": resource_name,
                                    "before_status": before_status,
                                    "after_status": after_status,
                                    "reason": f"Status still {after_status} after fix"
                                })
                    
                    success = tool_success and issues_resolved
                    
                    # Store attempt information
                    attempt_result = {
                        "attempt_number": attempt_num,
                        "fix_plan": fix_plan,
                        "execution_status": "SUCCESS" if success else "FAILED",
                        "tool_results": execution_results,
                        "before_metrics": before_metrics,
                        "after_metrics": after_metrics,
                        "issues_resolved": issues_resolved,
                        "failed_resources": failed_resources,
                        "tools_used": [step.get("tool_name") for step in fix_plan.get("steps", [])],
                        "interaction_id": interaction.get("id") if interaction else None
                    }
                    all_attempts.append(attempt_result)
                    
                    # If successful, break out of retry loop
                    if success:
                        logger.info(f"Fix successful on attempt {attempt_num}")
                        break
                    
                    # If not successful and more retries available, prepare for next attempt
                    if attempt < max_retries:
                        last_failure_info = {
                            "tools_used": attempt_result["tools_used"],
                            "result": attempt_result,
                            "failed_resources": failed_resources
                        }
                        logger.warning(f"Fix attempt {attempt_num} did not resolve issues. Retrying...")
                        # Update resource status for next attempt
                        resource_status = updated_resource_status
                        await asyncio.sleep(3)  # Wait a bit before retry
                    else:
                        logger.warning(f"All {max_retries + 1} fix attempts completed, but issues not fully resolved")
                
                except Exception as e:
                    logger.error(f"Error in fix attempt {attempt_num}: {e}", exc_info=True)
                    attempt_result = {
                        "attempt_number": attempt_num,
                        "execution_status": "FAILED",
                        "error": str(e)
                    }
                    all_attempts.append(attempt_result)
                    if attempt < max_retries:
                        await asyncio.sleep(3)  # Wait before retry
                    else:
                        break
            
            # Step 5: Store evaluation with all attempts
            final_success = all_attempts[-1].get("execution_status") == "SUCCESS" if all_attempts else False
            final_after_metrics = all_attempts[-1].get("after_metrics", {}) if all_attempts else {}
            
            fix_result = {
                "id": fix_id,
                "timestamp": datetime.utcnow().isoformat(),
                "fix_plan": all_attempts[-1].get("fix_plan", {}) if all_attempts else {},
                "execution_status": "SUCCESS" if final_success else "FAILED",
                "tool_results": all_attempts[-1].get("tool_results", []) if all_attempts else [],
                "before_metrics": original_before_metrics or {},
                "after_metrics": final_after_metrics,
                "interaction_id": all_attempts[-1].get("interaction_id") if all_attempts else None,
                "attempts": all_attempts,
                "total_attempts": len(all_attempts),
                "final_status": "SUCCESS" if final_success else "FAILED_AFTER_RETRIES"
            }
            
            await self.evaluation_store.store_fix_evaluation(fix_result)
            
            logger.info(f"Fix workflow completed: {fix_id} - Status: {fix_result['execution_status']} after {len(all_attempts)} attempt(s)")
            
            return fix_result
        
        except Exception as e:
            logger.error(f"Error in fix workflow: {e}", exc_info=True)
            return {
                "id": fix_id,
                "timestamp": datetime.utcnow().isoformat(),
                "execution_status": "FAILED",
                "error": str(e),
                "attempts": all_attempts,
                "total_attempts": len(all_attempts)
            }
    
    async def _capture_metrics(self, resource_status: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Capture current metrics from resources."""
        metrics = {}
        for resource in resource_status:
            metrics[resource["name"]] = {
                "status": resource["status"],
                "metrics": resource.get("metrics", {})
            }
        return metrics
