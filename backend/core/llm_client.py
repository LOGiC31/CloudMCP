"""LLM client for Gemini API interactions."""
import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from google import genai

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Client for interacting with Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM client."""
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = settings.GEMINI_MODEL
        self.interactions: List[Dict[str, Any]] = []
    
    async def analyze_and_plan(
        self,
        logs: List[Dict[str, Any]],
        app_config: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        resource_status: List[Dict[str, Any]],
        previous_attempt: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze failure logs and create a fix plan.
        
        Args:
            logs: List of log entries
            app_config: Application configuration
            available_tools: List of available MCP tools
            resource_status: Current resource status
            previous_attempt: Optional information about previous failed attempt
            
        Returns:
            Dictionary containing analysis and fix plan
        """
        start_time = time.time()
        logger.info(f"Starting LLM analysis - logs: {len(logs)}, resources: {len(resource_status)}, tools: {len(available_tools)}")
        if previous_attempt:
            logger.info(f"Retry attempt - previous attempt used tools: {previous_attempt.get('tools_used', [])}")
        
        # Format prompt
        prompt = self._build_analysis_prompt(logs, app_config, available_tools, resource_status, previous_attempt)
        
        try:
            # Call Gemini API (run in thread pool since it's blocking I/O)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
            )
            
            response_text = response.text
            logger.debug(f"LLM response received (length: {len(response_text)} chars)")
            
            # Parse response (expecting JSON)
            try:
                fix_plan = json.loads(response_text)
                logger.debug(f"Successfully parsed JSON fix plan with {len(fix_plan.get('steps', []))} steps")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response directly: {e}. Attempting to extract from markdown...")
                # If not JSON, try to extract JSON from markdown code blocks
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    fix_plan = json.loads(response_text[json_start:json_end].strip())
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    fix_plan = json.loads(response_text[json_start:json_end].strip())
                else:
                    # Fallback: create a structured response from text
                    fix_plan = {
                        "root_cause": response_text,
                        "reasoning": response_text,
                        "steps": [],
                        "tools_to_use": []
                    }
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Extract token usage from response
            tokens_used = 0
            try:
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    if hasattr(usage, 'total_token_count'):
                        tokens_used = usage.total_token_count
                    elif hasattr(usage, 'prompt_token_count') and hasattr(usage, 'candidates_token_count'):
                        tokens_used = usage.prompt_token_count + usage.candidates_token_count
            except Exception as e:
                logger.debug(f"Could not extract token usage: {e}")
            
            # Store interaction
            interaction = {
                "id": f"interaction_{int(time.time())}",
                "timestamp": datetime.utcnow().isoformat(),
                "prompt": prompt,
                "response": response_text,
                "fix_plan": fix_plan,
                "tokens_used": tokens_used,
                "duration_ms": duration_ms
            }
            self.interactions.append(interaction)
            
            logger.info(f"LLM analysis completed in {duration_ms}ms")
            return {
                "interaction": interaction,
                "fix_plan": fix_plan
            }
            
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}", exc_info=True)
            raise
    
    def _build_analysis_prompt(
        self,
        logs: List[Dict[str, Any]],
        app_config: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
        resource_status: List[Dict[str, Any]],
        previous_attempt: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the analysis prompt for the LLM."""
        
        # Format logs - prioritize logs from degraded resources
        error_logs = [log for log in logs if log.get("level") in ["ERROR", "CRITICAL", "WARNING"]]
        
        # Identify degraded resource names
        degraded_resource_names = {res.get('name') for res in resource_status if res.get('status') in ['DEGRADED', 'FAILED']}
        
        # Separate logs: prioritize logs from degraded resources, deprioritize others
        logs_from_degraded = []
        other_logs = []
        
        for log in error_logs:
            log_source = log.get('source', '').lower()
            log_message = log.get('message', '').lower()
            
            # Check if log is from a degraded resource
            is_from_degraded = any(
                res_name.lower() in log_source or res_name.lower() in log_message
                for res_name in degraded_resource_names
            )
            
            # Also check if log message mentions degraded resources
            if not is_from_degraded:
                is_from_degraded = any(
                    res_name.lower() in log_message
                    for res_name in degraded_resource_names
                )
            
            if is_from_degraded:
                logs_from_degraded.append(log)
            else:
                other_logs.append(log)
        
        # Build log summary: show degraded resource logs first, then others
        log_summary = ""
        if logs_from_degraded:
            log_summary += "⚠️ **Logs from DEGRADED/FAILED resources (HIGH PRIORITY):**\n"
            for log in logs_from_degraded[-15:]:  # Last 15 from degraded resources
                log_summary += f"[{log.get('timestamp')}] {log.get('level')}: {log.get('message')}\n"
            log_summary += "\n"
        
        if other_logs:
            log_summary += "📋 Other logs (lower priority):\n"
            for log in other_logs[-10:]:  # Last 10 other logs
                log_summary += f"[{log.get('timestamp')}] {log.get('level')}: {log.get('message')}\n"
        
        # Format tools
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}\n  Parameters: {tool.get('parameters', {})}"
            for tool in available_tools
        ])
        
        # Format resource status - emphasize DEGRADED/FAILED resources
        degraded_resources = [res for res in resource_status if res.get('status') in ['DEGRADED', 'FAILED']]
        healthy_resources = [res for res in resource_status if res.get('status') == 'HEALTHY']
        
        resource_summary = ""
        if degraded_resources:
            resource_summary += "⚠️ **DEGRADED/FAILED RESOURCES (MUST FIX THESE):**\n"
            for res in degraded_resources:
                metrics_info = ""
                if res.get('name') == 'postgres':
                    metrics = res.get('metrics', {})
                    conn_pct = metrics.get('connection_usage_percent', 0)
                    total = metrics.get('total_connections', 0)
                    max_conn = metrics.get('max_connections', 0)
                    metrics_info = f" (Connections: {total}/{max_conn} = {conn_pct:.1f}%)"
                elif res.get('name') == 'redis':
                    metrics = res.get('metrics', {})
                    mem_pct = metrics.get('redis_memory_usage_percent', 0)
                    metrics_info = f" (Memory: {mem_pct:.1f}%)"
                resource_summary += f"  - {res['name']} ({res['type']}): {res['status']}{metrics_info}\n"
            resource_summary += "\n"
        
        if healthy_resources:
            resource_summary += "✅ Healthy Resources:\n"
            for res in healthy_resources:
                resource_summary += f"  - {res['name']} ({res['type']}): {res['status']}\n"
        
        # Add previous attempt information if retrying
        previous_attempt_section = ""
        if previous_attempt:
            prev_tools = previous_attempt.get("tools_used", [])
            prev_failed = previous_attempt.get("failed_resources", [])
            prev_message = previous_attempt.get("message", "")
            
            previous_attempt_section = f"""
## Previous Attempt (Did Not Resolve Issue)
⚠️ A previous fix attempt was made but did not resolve the issue. Please try a different approach.

**Previous attempt details:**
- Tools used: {', '.join(prev_tools) if prev_tools else 'None'}
- Failed resources: {', '.join([f['resource'] for f in prev_failed]) if prev_failed else 'None'}
- Message: {prev_message}

**Important:** The previous approach did not work. Please:
1. Analyze why the previous fix didn't work
2. Try a different tool or approach
3. Consider alternative solutions (e.g., if restart didn't work, try flush/clear instead)

"""
        
        prompt = f"""You are an infrastructure orchestration AI agent. Analyze the following failure scenario and create a fix plan.

## Application Configuration
{json.dumps(app_config, indent=2)}

## Current Resource Status
{resource_summary}

## Error Logs
{log_summary}

## Available MCP Tools
{tools_description}
{previous_attempt_section}
## Task
1. **PRIORITY: Focus on DEGRADED/FAILED resources first.** These are the actual failures that need immediate fixing.
2. Analyze the logs and resource status to identify the root cause of the failure
3. **CRITICAL: If any resources are DEGRADED or FAILED, you MUST fix ALL of them. Each degraded resource needs at least one fix step. Do not skip any degraded resources.**
4. **Note:** Log warnings (like vm.overcommit_memory) are secondary concerns. If a resource is HEALTHY, do not prioritize fixing it over DEGRADED/FAILED resources.
5. **IMPORTANT: Tool Selection Guidelines:**
   - For PostgreSQL connection overload: Use `postgres_kill_long_queries` (works immediately) NOT `postgres_scale_connections` (doesn't work immediately)
   - For Redis memory issues: Use `redis_flush` (clears memory) or `redis_memory_purge` (evicts keys), NOT `redis_restart` (doesn't clear memory)
   - For Nginx connection overload: 
     * PRIMARY FIX: Use `nginx_scale_connections` to increase worker_connections limit (e.g., 200-300) to handle the load. This is the most effective solution when load generation is active.
     * SECONDARY FIX: Use `nginx_clear_connections` only if you need to clear connections temporarily, but note that connections will reconnect if load generation is still active.
     * AVOID `nginx_restart` (doesn't clear persistent connections from clients and doesn't scale capacity)
   - Always prefer tools that work immediately over tools that require manual intervention
6. Create a step-by-step fix plan using the available MCP tools
7. Return your response as JSON in the following format:

{{
    "root_cause": "Brief description of the root cause",
    "reasoning": "Detailed explanation of why this is the issue",
    "steps": [
        {{
            "tool_name": "name_of_tool",
            "parameters": {{"param1": "value1"}},
            "description": "What this step does"
        }}
    ],
    "tools_to_use": ["tool1", "tool2"]
}}

Be specific about which tools to use and what parameters to pass. Focus on fixing the root cause, not just symptoms.
{previous_attempt_section and "IMPORTANT: The previous attempt failed. Try a different approach or tool!"}
"""
        return prompt
    
    def get_interaction_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent LLM interactions."""
        return self.interactions[-limit:]
    
    def get_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific interaction by ID."""
        for interaction in self.interactions:
            if interaction["id"] == interaction_id:
                return interaction
        return None

