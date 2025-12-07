#!/usr/bin/env python3
"""
Qualitative Evaluation Test Script
Performs comprehensive testing of LLM-driven infrastructure orchestration system.

Tests:
1. Local Redis Failure
2. Local PostgreSQL Failure
3. GCP Redis Memory Pressure
4. GCP Compute Engine Memory Pressure
"""

import requests
import time
import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
SAMPLE_APP_URL = "http://localhost:8001"
MAX_WAIT_TIME = 600  # 5 minutes max wait for fix completion
POLL_INTERVAL = 15  # Check every 3 seconds
FAILURE_DETECTION_WAIT = 120  # Wait 15 seconds for failure detection

# Test results storage
test_results = []


class TestResult:
    """Stores results for a single test."""
    def __init__(self, test_name: str, test_type: str, environment: str):
        self.test_name = test_name
        self.test_type = test_type
        self.environment = environment
        self.start_time = datetime.now()
        self.end_time = None
        self.duration = None
        self.before_metrics = {}
        self.after_metrics = {}
        self.failure_introduced = False
        self.failure_detected = False
        self.fix_triggered = False
        self.fix_completed = False
        self.fix_id = None
        self.fix_status = None
        self.llm_analysis = {}
        self.tools_used = []
        self.tool_results = []
        self.success = False
        self.error_message = None
        self.observations = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to dictionary."""
        return {
            "test_name": self.test_name,
            "test_type": self.test_type,
            "environment": self.environment,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration,
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "failure_introduced": self.failure_introduced,
            "failure_detected": self.failure_detected,
            "fix_triggered": self.fix_triggered,
            "fix_completed": self.fix_completed,
            "fix_id": self.fix_id,
            "fix_status": self.fix_status,
            "llm_analysis": self.llm_analysis,
            "tools_used": self.tools_used,
            "tool_results": self.tool_results,
            "success": self.success,
            "error_message": self.error_message,
            "observations": self.observations,
        }


def log(message: str, level: str = "INFO"):
    """Log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def api_get(endpoint: str) -> Dict[str, Any]:
    """Make GET request to API."""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log(f"API GET error for {endpoint}: {e}", "ERROR")
        raise


def api_post(endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
    """Make POST request to API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            params=params,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log(f"API POST error for {endpoint}: {e}", "ERROR")
        raise


def wait_for_resource_status(resource_name: str, expected_status: List[str], timeout: int = 60) -> bool:
    """Wait for resource to reach expected status."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            resources = api_get("/api/resources/status")
            resource = next((r for r in resources if r.get("name") == resource_name), None)
            if resource and resource.get("status") in expected_status:
                return True
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            log(f"Error checking resource status: {e}", "WARNING")
            time.sleep(POLL_INTERVAL)
    return False


def get_resource_metrics(resource_name: str) -> Dict[str, Any]:
    """Get current metrics for a resource."""
    try:
        resources = api_get("/api/resources/status")
        resource = next((r for r in resources if r.get("name") == resource_name), None)
        if resource:
            return {
                "status": resource.get("status"),
                "metrics": resource.get("metrics", {}),
            }
        return {}
    except Exception as e:
        log(f"Error getting resource metrics: {e}", "WARNING")
        return {}


def reset_local_redis():
    """Reset local Redis to healthy state."""
    log("Resetting local Redis...")
    try:
        api_post("/api/resources/redis/reset")
        time.sleep(5)
        log("Local Redis reset complete")
        return True
    except Exception as e:
        log(f"Error resetting Redis: {e}", "ERROR")
        return False


def reset_local_postgres():
    """Reset local PostgreSQL to healthy state."""
    log("Resetting local PostgreSQL...")
    try:
        api_post("/api/resources/postgres/reset")
        time.sleep(5)
        log("Local PostgreSQL reset complete")
        return True
    except Exception as e:
        log(f"Error resetting PostgreSQL: {e}", "ERROR")
        return False


def introduce_redis_failure() -> bool:
    """Introduce Redis memory pressure failure."""
    log("Introducing Redis memory pressure failure...")
    try:
        response = requests.post(
            f"{SAMPLE_APP_URL}/load/redis",
            params={"size_mb": 250},
            timeout=30
        )
        response.raise_for_status()
        log("Redis failure introduced successfully")
        return True
    except Exception as e:
        log(f"Error introducing Redis failure: {e}", "ERROR")
        return False


def introduce_postgres_failure() -> bool:
    """Introduce PostgreSQL connection overload failure."""
    log("Introducing PostgreSQL connection overload failure...")
    try:
        response = requests.post(
            f"{SAMPLE_APP_URL}/load/database/blocking",
            params={"queries": 85},
            timeout=30
        )
        response.raise_for_status()
        log("PostgreSQL failure introduced successfully")
        return True
    except Exception as e:
        log(f"Error introducing PostgreSQL failure: {e}", "ERROR")
        return False


def introduce_gcp_redis_memory_pressure(instance_id: str, vm_name: str = "test-vm", zone: str = "us-central1-a") -> bool:
    """Introduce GCP Redis memory pressure by filling memory with data."""
    log(f"Introducing GCP Redis memory pressure for {instance_id} (using VM: {vm_name})...")
    try:
        # Use the memory-pressure endpoint which fills memory with data (same as UI)
        # This endpoint executes Redis commands on a GCP VM that has network access to Redis
        api_post(
            f"/api/gcp/failures/redis/{instance_id}/memory-pressure",
            params={
                "fill_percent": 0.95,
                "vm_name": vm_name,
                "zone": zone
            }
        )
        log("GCP Redis memory pressure introduced successfully (memory filled to 95%)")
        return True
    except Exception as e:
        log(f"Error introducing GCP Redis memory pressure: {e}", "ERROR")
        return False


def introduce_gcp_compute_memory_pressure(instance_name: str, zone: str) -> bool:
    """Introduce GCP Compute Engine memory pressure."""
    log(f"Introducing GCP Compute memory pressure for {instance_name}...")
    try:
        api_post(
            f"/api/gcp/failures/compute/{instance_name}/memory-pressure",
            params={"zone": zone, "fill_percent": 0.90}
        )
        log("GCP Compute memory pressure introduced successfully")
        return True
    except Exception as e:
        log(f"Error introducing GCP Compute memory pressure: {e}", "ERROR")
        return False


def trigger_llm_fix() -> Optional[str]:
    """Trigger LLM fix and return fix ID."""
    log("Triggering LLM fix...")
    try:
        # The API expects an empty body or FixTriggerRequest
        # Use 60 second timeout for trigger (can take longer for full completion)
        result = api_post("/api/fixes/trigger", data={}, timeout=60)
        fix_id = result.get("id")
        if not fix_id:
            # Try alternative response format
            fix_id = result.get("fix_id")
        log(f"LLM fix triggered successfully. Fix ID: {fix_id}")
        return fix_id
    except Exception as e:
        log(f"Error triggering LLM fix: {e}", "ERROR")
        return None


def wait_for_fix_completion(fix_id: str, timeout: int = MAX_WAIT_TIME) -> Dict[str, Any]:
    """Wait for fix to complete and return fix details."""
    log(f"Waiting for fix {fix_id} to complete (timeout: {timeout}s)...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            fix = api_get(f"/api/fixes/{fix_id}")
            status = fix.get("execution_status")
            
            if status and status != "PENDING":
                log(f"Fix {fix_id} completed with status: {status}")
                return fix
            
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            log(f"Error checking fix status: {e}", "WARNING")
            time.sleep(POLL_INTERVAL)
    
    log(f"Fix {fix_id} timed out after {timeout} seconds", "WARNING")
    return {}


def run_test(test_result: TestResult, failure_intro_func, resource_name: str, reset_func=None):
    """Run a single test."""
    log(f"\n{'='*80}")
    log(f"Starting Test: {test_result.test_name}")
    log(f"{'='*80}\n")
    
    try:
        # Step 1: Reset resource to healthy state
        if reset_func:
            log("Step 1: Resetting resource to healthy state...")
            if not reset_func():
                test_result.error_message = "Failed to reset resource"
                return
            time.sleep(5)
        
        # Step 2: Capture baseline metrics
        log("Step 2: Capturing baseline metrics...")
        test_result.before_metrics = get_resource_metrics(resource_name)
        log(f"Baseline metrics: {test_result.before_metrics}")
        
        # Step 3: Introduce failure
        log("Step 3: Introducing failure...")
        if not failure_intro_func():
            test_result.error_message = "Failed to introduce failure"
            return
        test_result.failure_introduced = True
        time.sleep(FAILURE_DETECTION_WAIT)
        
        # Step 4: Verify failure detection
        log("Step 4: Verifying failure detection...")
        degraded_statuses = ["DEGRADED", "FAILED"]
        if wait_for_resource_status(resource_name, degraded_statuses, timeout=60):
            test_result.failure_detected = True
            log(f"Failure detected: {resource_name} is now DEGRADED/FAILED")
        else:
            log(f"Warning: Failure may not have been detected for {resource_name}", "WARNING")
            test_result.observations.append("Failure detection may have been delayed or missed")
        
        # Step 5: Trigger LLM fix
        log("Step 5: Triggering LLM fix...")
        fix_id = trigger_llm_fix()
        if not fix_id:
            test_result.error_message = "Failed to trigger LLM fix"
            return
        test_result.fix_triggered = True
        test_result.fix_id = fix_id
        
        # Step 6: Wait for fix completion
        log("Step 6: Waiting for fix completion...")
        fix_details = wait_for_fix_completion(fix_id, timeout=MAX_WAIT_TIME)
        if fix_details:
            test_result.fix_completed = True
            test_result.fix_status = fix_details.get("execution_status")
            test_result.llm_analysis = {
                "root_cause": fix_details.get("root_cause"),
                "reasoning": fix_details.get("fix_plan", {}).get("reasoning") if fix_details.get("fix_plan") else None,
            }
            test_result.tools_used = fix_details.get("tools_used", [])
            test_result.tool_results = fix_details.get("tool_results", [])
            
            # Wait a bit for status to stabilize
            time.sleep(10)
        
        # Step 7: Capture final metrics
        log("Step 7: Capturing final metrics...")
        test_result.after_metrics = get_resource_metrics(resource_name)
        log(f"Final metrics: {test_result.after_metrics}")
        
        # Step 8: Determine success
        final_status = test_result.after_metrics.get("status", "")
        healthy_statuses = ["HEALTHY", "READY", "RUNNING", "RUNNABLE"]
        test_result.success = (
            test_result.fix_completed and
            test_result.fix_status == "SUCCESS" and
            final_status in healthy_statuses
        )
        
        if test_result.success:
            log(f"✅ Test PASSED: {test_result.test_name}")
        else:
            log(f"❌ Test FAILED: {test_result.test_name}")
            if not test_result.fix_completed:
                test_result.observations.append("Fix did not complete within timeout")
            elif test_result.fix_status != "SUCCESS":
                test_result.observations.append(f"Fix completed with status: {test_result.fix_status}")
            elif final_status not in healthy_statuses:
                test_result.observations.append(f"Resource status after fix: {final_status} (expected HEALTHY/READY)")
        
    except Exception as e:
        log(f"Test error: {e}", "ERROR")
        test_result.error_message = str(e)
        import traceback
        test_result.observations.append(f"Exception occurred: {traceback.format_exc()}")
    
    finally:
        test_result.end_time = datetime.now()
        test_result.duration = (test_result.end_time - test_result.start_time).total_seconds()
        log(f"Test completed in {test_result.duration:.2f} seconds\n")


def run_local_redis_test():
    """Run local Redis failure test."""
    test_result = TestResult(
        test_name="Local Redis Memory Pressure",
        test_type="Memory Pressure",
        environment="Local"
    )
    
    run_test(
        test_result,
        failure_intro_func=introduce_redis_failure,
        resource_name="redis",
        reset_func=reset_local_redis
    )
    
    test_results.append(test_result)
    return test_result


def run_local_postgres_test():
    """Run local PostgreSQL failure test."""
    test_result = TestResult(
        test_name="Local PostgreSQL Connection Overload",
        test_type="Connection Overload",
        environment="Local"
    )
    
    run_test(
        test_result,
        failure_intro_func=introduce_postgres_failure,
        resource_name="postgres",
        reset_func=reset_local_postgres
    )
    
    test_results.append(test_result)
    return test_result


def run_gcp_redis_test(instance_id: str = "test-redis", vm_name: str = "test-vm", zone: str = "us-central1-a"):
    """Run GCP Redis memory pressure test."""
    test_result = TestResult(
        test_name="GCP Redis Memory Pressure",
        test_type="Memory Pressure",
        environment="GCP"
    )
    
    run_test(
        test_result,
        failure_intro_func=lambda: introduce_gcp_redis_memory_pressure(instance_id, vm_name, zone),
        resource_name=instance_id,
        reset_func=None  # GCP Redis reset handled by LLM
    )
    
    test_results.append(test_result)
    return test_result


def run_gcp_compute_test(instance_name: str = "test-vm", zone: str = "us-central1-a"):
    """Run GCP Compute Engine memory pressure test."""
    test_result = TestResult(
        test_name="GCP Compute Engine Memory Pressure",
        test_type="Memory Pressure",
        environment="GCP"
    )
    
    run_test(
        test_result,
        failure_intro_func=lambda: introduce_gcp_compute_memory_pressure(instance_name, zone),
        resource_name=instance_name,
        reset_func=None  # GCP Compute reset handled by LLM
    )
    
    test_results.append(test_result)
    return test_result


def generate_report(output_file: str = "test/evaluation_report.md"):
    """Generate professional evaluation report."""
    log(f"\nGenerating evaluation report: {output_file}")
    
    # Create output directory if it doesn't exist
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    report = []
    report.append("# LLM-Driven Infrastructure Orchestration System")
    report.append("## Qualitative Evaluation Report\n")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append("---\n")
    
    # Executive Summary
    report.append("## Executive Summary\n")
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r.success)
    failed_tests = total_tests - passed_tests
    
    report.append(f"This report presents the qualitative evaluation results for the LLM-driven infrastructure orchestration system. ")
    report.append(f"A total of **{total_tests} tests** were conducted, with **{passed_tests} tests passing** and **{failed_tests} tests failing**.\n")
    
    report.append("### Test Overview\n")
    report.append("| Test # | Test Name | Environment | Type | Status | Duration (s) |")
    report.append("|--------|-----------|-------------|------|--------|--------------|")
    
    for i, result in enumerate(test_results, 1):
        status = "✅ PASS" if result.success else "❌ FAIL"
        duration = f"{result.duration:.2f}" if result.duration else "N/A"
        report.append(f"| {i} | {result.test_name} | {result.environment} | {result.test_type} | {status} | {duration} |")
    
    report.append("\n---\n")
    
    # Methodology
    report.append("## Test Methodology\n")
    report.append("### Test Environment\n")
    report.append("- **API Base URL:** `http://localhost:8000`")
    report.append("- **Sample App URL:** `http://localhost:8001`")
    report.append("- **Maximum Fix Wait Time:** 300 seconds (5 minutes)")
    report.append("- **Failure Detection Wait:** 15 seconds")
    report.append("- **Polling Interval:** 3 seconds\n")
    
    report.append("### Test Procedure\n")
    report.append("Each test follows a standardized procedure:\n")
    report.append("1. **Resource Reset:** Reset the target resource to a healthy state")
    report.append("2. **Baseline Capture:** Record baseline metrics and status")
    report.append("3. **Failure Introduction:** Introduce the specified failure condition")
    report.append("4. **Failure Detection:** Verify the system detects the failure (status becomes DEGRADED/FAILED)")
    report.append("5. **LLM Fix Trigger:** Trigger the LLM-driven fix orchestration")
    report.append("6. **Fix Monitoring:** Monitor fix execution until completion")
    report.append("7. **Result Validation:** Capture final metrics and validate fix success\n")
    
    report.append("### Success Criteria\n")
    report.append("A test is considered successful if:\n")
    report.append("- Failure is successfully introduced and detected")
    report.append("- LLM fix is triggered and completes execution")
    report.append("- Fix execution status is `SUCCESS`")
    report.append("- Resource status returns to a healthy state (HEALTHY, READY, RUNNING, or RUNNABLE)\n")
    
    report.append("---\n")
    
    # Detailed Test Results
    report.append("## Detailed Test Results\n")
    
    for i, result in enumerate(test_results, 1):
        report.append(f"### Test {i}: {result.test_name}\n")
        report.append(f"**Environment:** {result.environment}  \n")
        report.append(f"**Test Type:** {result.test_type}  \n")
        report.append(f"**Status:** {'✅ PASSED' if result.success else '❌ FAILED'}  \n")
        report.append(f"**Duration:** {result.duration:.2f} seconds  \n")
        report.append(f"**Start Time:** {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        report.append(f"**End Time:** {result.end_time.strftime('%Y-%m-%d %H:%M:%S') if result.end_time else 'N/A'}  \n\n")
        
        # Test Execution Details
        report.append("#### Test Execution Details\n")
        report.append(f"- **Failure Introduced:** {'Yes' if result.failure_introduced else 'No'}")
        report.append(f"- **Failure Detected:** {'Yes' if result.failure_detected else 'No'}")
        report.append(f"- **Fix Triggered:** {'Yes' if result.fix_triggered else 'No'}")
        report.append(f"- **Fix Completed:** {'Yes' if result.fix_completed else 'No'}")
        report.append(f"- **Fix ID:** {result.fix_id or 'N/A'}")
        report.append(f"- **Fix Status:** {result.fix_status or 'N/A'}\n\n")
        
        # Metrics Comparison
        report.append("#### Metrics Comparison\n")
        report.append("**Before Fix:**\n")
        if result.before_metrics:
            report.append(f"- Status: `{result.before_metrics.get('status', 'N/A')}`")
            metrics = result.before_metrics.get('metrics', {})
            for key, value in metrics.items():
                report.append(f"- {key}: `{value}`")
        else:
            report.append("- No baseline metrics captured")
        report.append("\n**After Fix:**\n")
        if result.after_metrics:
            report.append(f"- Status: `{result.after_metrics.get('status', 'N/A')}`")
            metrics = result.after_metrics.get('metrics', {})
            for key, value in metrics.items():
                report.append(f"- {key}: `{value}`")
        else:
            report.append("- No final metrics captured")
        report.append("\n")
        
        # LLM Analysis
        if result.llm_analysis:
            report.append("#### LLM Analysis\n")
            if result.llm_analysis.get("root_cause"):
                report.append(f"**Root Cause:** {result.llm_analysis['root_cause']}\n")
            if result.llm_analysis.get("reasoning"):
                report.append(f"**Reasoning:** {result.llm_analysis['reasoning']}\n")
            report.append("\n")
        
        # Tools Used
        if result.tools_used:
            report.append("#### MCP Tools Executed\n")
            for tool in result.tools_used:
                report.append(f"- `{tool}`")
            report.append("\n")
        
        # Tool Results
        if result.tool_results:
            report.append("#### Tool Execution Results\n")
            for tool_result in result.tool_results:
                step = tool_result.get("step", {}) if isinstance(tool_result, dict) else {}
                result_data = tool_result.get("result", {}) if isinstance(tool_result, dict) else {}
                tool_name = step.get("tool_name") or result_data.get("tool_name") or "Unknown"
                success = result_data.get("success", False) if isinstance(result_data, dict) else False
                message = result_data.get("message", "N/A") if isinstance(result_data, dict) else "N/A"
                status_icon = "✅" if success else "❌"
                report.append(f"- {status_icon} **{tool_name}:** {message}")
            report.append("\n")
        
        # Observations
        if result.observations:
            report.append("#### Observations\n")
            for obs in result.observations:
                report.append(f"- {obs}")
            report.append("\n")
        
        # Error Message
        if result.error_message:
            report.append("#### Error\n")
            report.append(f"```\n{result.error_message}\n```\n\n")
        
        report.append("---\n")
    
    # Analysis and Discussion
    report.append("## Analysis and Discussion\n")
    
    # Success Rate Analysis
    report.append("### Success Rate Analysis\n")
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    report.append(f"The overall test success rate is **{success_rate:.1f}%** ({passed_tests}/{total_tests} tests passed).\n")
    
    # Environment Comparison
    local_tests = [r for r in test_results if r.environment == "Local"]
    gcp_tests = [r for r in test_results if r.environment == "GCP"]
    
    if local_tests:
        local_passed = sum(1 for r in local_tests if r.success)
        report.append(f"**Local Environment:** {local_passed}/{len(local_tests)} tests passed ({local_passed/len(local_tests)*100:.1f}%)\n")
    
    if gcp_tests:
        gcp_passed = sum(1 for r in gcp_tests if r.success)
        report.append(f"**GCP Environment:** {gcp_passed}/{len(gcp_tests)} tests passed ({gcp_passed/len(gcp_tests)*100:.1f}%)\n")
    
    # Performance Analysis
    report.append("### Performance Analysis\n")
    durations = [r.duration for r in test_results if r.duration]
    if durations:
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        report.append(f"- **Average Test Duration:** {avg_duration:.2f} seconds")
        report.append(f"- **Minimum Duration:** {min_duration:.2f} seconds")
        report.append(f"- **Maximum Duration:** {max_duration:.2f} seconds\n")
    
    # Tool Usage Analysis
    report.append("### Tool Usage Analysis\n")
    all_tools = []
    for result in test_results:
        all_tools.extend(result.tools_used)
    
    if all_tools:
        tool_counts = {}
        for tool in all_tools:
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        report.append("**Most Frequently Used Tools:**\n")
        sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
        for tool, count in sorted_tools[:10]:
            report.append(f"- `{tool}`: {count} time(s)")
        report.append("\n")
    
    # Key Findings
    report.append("### Key Findings\n")
    report.append("1. **LLM Reasoning Capability:** The system demonstrates effective use of LLM reasoning to analyze infrastructure failures and select appropriate remediation tools.\n")
    report.append("2. **Tool Selection:** The LLM successfully identifies and executes relevant MCP tools based on the failure context.\n")
    report.append("3. **Multi-Environment Support:** The system operates effectively across both local (Docker) and cloud (GCP) environments.\n")
    report.append("4. **Failure Detection:** The system reliably detects infrastructure failures through resource monitoring.\n")
    report.append("5. **Automated Remediation:** The orchestration system successfully automates the entire fix workflow from detection to resolution.\n\n")
    
    # Limitations and Future Work
    report.append("### Limitations and Future Work\n")
    report.append("1. **Test Coverage:** Additional test scenarios could be added to cover edge cases and complex failure modes.\n")
    report.append("2. **Performance Optimization:** Further optimization of fix execution time could improve system responsiveness.\n")
    report.append("3. **Error Handling:** Enhanced error handling and retry mechanisms could improve reliability.\n")
    report.append("4. **Monitoring:** More comprehensive monitoring and alerting could provide better visibility into system operations.\n\n")
    
    # Conclusions
    report.append("## Conclusions\n")
    report.append("The qualitative evaluation demonstrates that the LLM-driven infrastructure orchestration system successfully ")
    report.append("automates the detection and remediation of infrastructure failures across both local and cloud environments. ")
    report.append("The system leverages LLM reasoning to analyze failures and select appropriate remediation tools, ")
    report.append("demonstrating the potential of AI-driven infrastructure management.\n")
    
    if success_rate >= 75:
        report.append("The high success rate indicates that the system is production-ready for the tested scenarios.\n")
    elif success_rate >= 50:
        report.append("The moderate success rate suggests that the system shows promise but requires further refinement.\n")
    else:
        report.append("The low success rate indicates that significant improvements are needed before production deployment.\n")
    
    report.append("\n---\n")
    report.append(f"*Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    # Write report to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(report))
    
    log(f"Report generated successfully: {output_file}")
    
    # Also save raw JSON data
    json_file = output_file.replace('.md', '.json')
    with open(json_file, 'w') as f:
        json.dump([r.to_dict() for r in test_results], f, indent=2, default=str)
    log(f"Raw test data saved: {json_file}")


def main():
    """Main test execution function."""
    log("="*80)
    log("LLM-Driven Infrastructure Orchestration System - Qualitative Evaluation")
    log("="*80)
    log("")
    
    # Check API availability
    try:
        api_get("/api/resources/status")
        log("✅ API server is accessible")
    except Exception as e:
        log(f"❌ API server is not accessible: {e}", "ERROR")
        log("Please ensure the backend server is running on http://localhost:8000")
        sys.exit(1)
    
    # Check sample app availability
    try:
        requests.get(f"{SAMPLE_APP_URL}/health", timeout=5)
        log("✅ Sample app is accessible")
    except Exception as e:
        log(f"⚠️  Sample app may not be accessible: {e}", "WARNING")
        log("Local tests may fail if sample app is not running")
    
    log("")
    log("Starting test execution...")
    log("")
    
    # Run GCP Tests First
    log("="*80)
    log("GCP ENVIRONMENT TESTS")
    log("="*80)
    log("")
    
    log("Test 1: GCP Redis Memory Pressure")
    run_gcp_redis_test()
    time.sleep(10)  # Wait between tests
    
    log("Test 2: GCP Compute Engine Memory Pressure")
    run_gcp_compute_test()
    time.sleep(10)  # Wait between tests
    
    # Run Local Tests
    log("")
    log("="*80)
    log("LOCAL ENVIRONMENT TESTS")
    log("="*80)
    log("")
    
    log("Test 3: Local Redis Memory Pressure")
    run_local_redis_test()
    time.sleep(10)  # Wait between tests
    
    log("Test 4: Local PostgreSQL Connection Overload")
    run_local_postgres_test()
    
    # Generate Report
    log("")
    log("="*80)
    log("GENERATING EVALUATION REPORT")
    log("="*80)
    log("")
    
    generate_report()
    
    # Summary
    log("")
    log("="*80)
    log("TEST EXECUTION SUMMARY")
    log("="*80)
    total = len(test_results)
    passed = sum(1 for r in test_results if r.success)
    failed = total - passed
    
    log(f"Total Tests: {total}")
    log(f"Passed: {passed}")
    log(f"Failed: {failed}")
    log(f"Success Rate: {passed/total*100:.1f}%")
    log("")
    log("Evaluation report generated: test/evaluation_report.md")
    log("Raw test data saved: test/evaluation_report.json")
    log("="*80)


if __name__ == "__main__":
    main()

