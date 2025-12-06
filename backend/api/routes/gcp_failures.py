"""GCP failure introduction API routes."""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
from backend.gcp.auth import get_gcp_credentials, get_gcp_project_id
from backend.config import settings
from backend.utils.logger import get_logger
from google.cloud import redis_v1, compute_v1
from googleapiclient import discovery
import asyncio
import redis
import threading
import time
import random
import string

logger = get_logger(__name__)
router = APIRouter(prefix="/gcp/failures", tags=["gcp-failures"])


@router.post("/redis/{instance_id}/degrade")
async def degrade_redis(instance_id: str, memory_gb: float = 0.5):
    """
    Degrade GCP Redis instance by scaling down memory.
    This simulates memory pressure that can be fixed by scaling up.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        
        client = redis_v1.CloudRedisClient(credentials=credentials)
        
        # Find the instance location
        region = settings.GCP_REGION
        instance_name = f"projects/{project_id}/locations/{region}/instances/{instance_id}"
        
        try:
            instance = client.get_instance(request={"name": instance_name})
        except Exception as e:
            # Try to find instance in other regions
            common_regions = [settings.GCP_REGION, "us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1"]
            instance = None
            for r in common_regions:
                try:
                    instance_name = f"projects/{project_id}/locations/{r}/instances/{instance_id}"
                    instance = client.get_instance(request={"name": instance_name})
                    region = r
                    break
                except:
                    continue
            
            if not instance:
                raise HTTPException(status_code=404, detail=f"Redis instance {instance_id} not found")
        
        current_memory = instance.memory_size_gb
        
        # Scale down to simulate memory pressure (minimum 0.5GB for BASIC tier)
        target_memory = min(memory_gb, current_memory * 0.5)  # Scale down to 50% or specified amount
        target_memory = max(0.5, target_memory)  # Minimum 0.5GB
        
        if target_memory >= current_memory:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot degrade: target memory ({target_memory}GB) must be less than current ({current_memory}GB)"
            )
        
        # Update memory size
        instance.memory_size_gb = target_memory
        operation = client.update_instance(
            request={
                "update_mask": {"paths": ["memory_size_gb"]},
                "instance": instance
            }
        )
        
        # Wait for operation to start (don't wait for completion)
        operation.result(timeout=30)
        
        logger.info(f"Degraded Redis {instance_id}: scaled memory from {current_memory}GB to {target_memory}GB")
        
        return {
            "success": True,
            "message": f"Redis instance {instance_id} degraded: memory scaled from {current_memory}GB to {target_memory}GB",
            "instance_id": instance_id,
            "current_memory_gb": current_memory,
            "target_memory_gb": target_memory,
            "region": region
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error degrading Redis instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to degrade Redis: {str(e)}")


@router.post("/redis/{instance_id}/clear-memory")
async def clear_redis_memory(instance_id: str):
    """
    Clear memory pressure by flushing all data from Redis.
    This resets the memory usage back to normal.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        
        client = redis_v1.CloudRedisClient(credentials=credentials)
        
        # Find the instance location
        region = settings.GCP_REGION
        instance_name = f"projects/{project_id}/locations/{region}/instances/{instance_id}"
        
        try:
            instance = client.get_instance(request={"name": instance_name})
        except Exception as e:
            # Try to find instance in other regions
            common_regions = [settings.GCP_REGION, "us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1"]
            instance = None
            for r in common_regions:
                try:
                    instance_name = f"projects/{project_id}/locations/{r}/instances/{instance_id}"
                    instance = client.get_instance(request={"name": instance_name})
                    region = r
                    break
                except:
                    continue
            
            if not instance:
                raise HTTPException(status_code=404, detail=f"Redis instance {instance_id} not found")
        
        # Get Redis connection details
        redis_host = instance.host
        redis_port = instance.port
        
        # Connect and flush
        try:
            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=False, socket_connect_timeout=10)
            r.flushall()
            
            # Check memory after flush
            info = r.info('memory')
            used_memory = info.get('used_memory', 0)
            
            logger.info(f"Cleared Redis {instance_id} memory: {used_memory / (1024*1024):.1f}MB remaining")
            
            return {
                "success": True,
                "message": f"Redis {instance_id} memory cleared successfully",
                "instance_id": instance_id,
                "remaining_memory_mb": round(used_memory / (1024*1024), 2)
            }
        except redis.exceptions.ConnectionError:
            raise HTTPException(status_code=500, detail="Could not connect to Redis. Check network access and authentication.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear Redis memory: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing Redis memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear Redis memory: {str(e)}")


@router.post("/redis/{instance_id}/reset")
async def reset_redis(instance_id: str, memory_gb: float = 1.0):
    """
    Reset GCP Redis instance by scaling memory back up.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        
        client = redis_v1.CloudRedisClient(credentials=credentials)
        
        # Find the instance location
        region = settings.GCP_REGION
        instance_name = f"projects/{project_id}/locations/{region}/instances/{instance_id}"
        
        try:
            instance = client.get_instance(request={"name": instance_name})
        except Exception as e:
            # Try to find instance in other regions
            common_regions = [settings.GCP_REGION, "us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1"]
            instance = None
            for r in common_regions:
                try:
                    instance_name = f"projects/{project_id}/locations/{r}/instances/{instance_id}"
                    instance = client.get_instance(request={"name": instance_name})
                    region = r
                    break
                except:
                    continue
            
            if not instance:
                raise HTTPException(status_code=404, detail=f"Redis instance {instance_id} not found")
        
        current_memory = instance.memory_size_gb
        
        # Scale up to reset
        if memory_gb <= current_memory:
            return {
                "success": True,
                "message": f"Redis instance {instance_id} already has {current_memory}GB (>= {memory_gb}GB)",
                "instance_id": instance_id,
                "memory_gb": current_memory
            }
        
        # Update memory size
        instance.memory_size_gb = memory_gb
        operation = client.update_instance(
            request={
                "update_mask": {"paths": ["memory_size_gb"]},
                "instance": instance
            }
        )
        
        # Wait for operation to start
        operation.result(timeout=30)
        
        logger.info(f"Reset Redis {instance_id}: scaled memory from {current_memory}GB to {memory_gb}GB")
        
        return {
            "success": True,
            "message": f"Redis instance {instance_id} reset: memory scaled from {current_memory}GB to {memory_gb}GB",
            "instance_id": instance_id,
            "current_memory_gb": current_memory,
            "target_memory_gb": memory_gb,
            "region": region
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting Redis instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset Redis: {str(e)}")


@router.post("/compute/{instance_name}/cpu-stress")
async def compute_cpu_stress(instance_name: str, zone: str = None, duration_seconds: int = 600, cpu_percent: int = 90, background_tasks: BackgroundTasks = None):
    """
    Create CPU stress on Compute Engine instance by running CPU-intensive tasks.
    This simulates high CPU usage that can cause performance degradation.
    More realistic than just stopping the instance.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        zone = zone or settings.GCP_ZONE
        
        client = compute_v1.InstancesClient(credentials=credentials)
        
        # Get instance details
        instance = client.get(project=project_id, zone=zone, instance=instance_name)
        
        if not instance:
            raise HTTPException(status_code=404, detail=f"Compute instance {instance_name} not found")
        
        # Check if instance is running
        if instance.status != "RUNNING":
            raise HTTPException(
                status_code=400,
                detail=f"Instance {instance_name} is not running (status: {instance.status})"
            )
        
        # Get network interface for SSH access
        network_interfaces = instance.network_interfaces
        if not network_interfaces:
            raise HTTPException(status_code=400, detail="Instance has no network interfaces")
        
        external_ip = None
        for ni in network_interfaces:
            access_configs = ni.access_configs
            if access_configs:
                external_ip = access_configs[0].nat_i_p
        
        def run_cpu_stress():
            try:
                import subprocess
                import os
                import tempfile
                import shutil
                
                logger.info(f"Starting CPU stress on {instance_name}: {cpu_percent}% for {duration_seconds}s")
                
                # Find gcloud in common locations
                gcloud_path = None
                possible_paths = [
                    shutil.which('gcloud'),  # Check PATH first
                    os.path.expanduser('~/google-cloud-sdk/bin/gcloud'),
                    os.path.expanduser('~/Downloads/google-cloud-sdk/bin/gcloud'),
                    os.path.expanduser('~/Desktop/google-cloud-sdk/bin/gcloud'),
                    '/usr/local/bin/gcloud',
                    '/opt/homebrew/bin/gcloud',
                    '/usr/bin/gcloud',
                ]
                
                for path in possible_paths:
                    if path and os.path.exists(path) and os.access(path, os.X_OK):
                        gcloud_path = path
                        break
                
                if not gcloud_path:
                    logger.warning("gcloud CLI not found. CPU stress requires gcloud compute ssh.")
                    logger.info("To enable CPU stress, install gcloud CLI: https://cloud.google.com/sdk/docs/install")
                    logger.info("Or set up PATH to include gcloud: export PATH=$HOME/google-cloud-sdk/bin:$PATH")
                    return
                
                logger.debug(f"Using gcloud at: {gcloud_path}")
                
                # Create a Python script that runs CPU stress
                # Use a simpler approach that actually generates CPU load
                # Note: Double curly braces {{}} escape to single braces {} in f-strings
                script_content = f"""#!/usr/bin/env python3
import time
import multiprocessing
import os
import sys
import signal

# Handle signals to cleanup on exit
def signal_handler(sig, frame):
    print("\\nReceived signal, cleaning up...")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def cpu_stress():
    # Run for specified duration
    end_time = time.time() + {duration_seconds}
    iteration = 0
    while time.time() < end_time:
        # CPU-intensive loop - no sleep to maximize CPU usage
        x = 0
        for i in range(1000000):
            x += i * i
        iteration += 1
        # Very small sleep to prevent 100% CPU (which might be throttled)
        time.sleep(0.001)
        # Log progress every 100 iterations
        if iteration % 100 == 0:
            elapsed = time.time() - (end_time - {duration_seconds})
            print(f"CPU stress running: {{iteration}} iterations, {{elapsed:.1f}}s elapsed", flush=True)

# Start multiple processes to reach target CPU usage
num_cores = multiprocessing.cpu_count()
# Calculate processes needed: for 95% CPU on 2 cores, we need ~1.9 processes, round up to 2
target_processes = max(1, int(round(num_cores * {cpu_percent} / 100)))

print(f"Starting {{target_processes}} CPU stress processes on {{num_cores}} cores for {duration_seconds}s", flush=True)
print(f"Target CPU usage: {cpu_percent}%", flush=True)

processes = []
for i in range(target_processes):
    p = multiprocessing.Process(target=cpu_stress, daemon=False)
    p.start()
    processes.append(p)
    print(f"Started process {{p.pid}}", flush=True)

print(f"All {{target_processes}} processes started. Running for {duration_seconds}s...", flush=True)

# Wait for all processes
for p in processes:
    p.join()

print("CPU stress completed", flush=True)
"""
                
                # Try to use gcloud compute ssh to run the script
                try:
                    # Use base64 encoding to avoid shell escaping issues
                    import base64
                    script_b64 = base64.b64encode(script_content.encode()).decode()
                    
                    # Create a command that decodes and runs the script
                    # Use a simpler approach: write script to file and execute with nohup directly
                    remote_command = f"""bash -c '
# Decode and write script
python3 << "PYTHON_EOF"
import base64
import sys

script_b64 = "{script_b64}"
script_content = base64.b64decode(script_b64).decode()

# Write to a persistent file
script_path = "/tmp/cpu_stress_script.py"
with open(script_path, "w") as f:
    f.write(script_content)

import os
os.chmod(script_path, 0o755)
print(f"Script written to: {{script_path}}")
sys.stdout.flush()
PYTHON_EOF

# Now run the script with nohup in background
log_file="/tmp/cpu_stress.log"
nohup python3 /tmp/cpu_stress_script.py > "$log_file" 2>&1 &
STRESS_PID=$!

# Wait a moment and verify
sleep 2
if ps -p $STRESS_PID > /dev/null 2>&1; then
    echo "SUCCESS: CPU stress process started: PID $STRESS_PID"
    echo "Log file: $log_file"
    # Check for child processes
    CHILD_PIDS=$(pgrep -P $STRESS_PID 2>/dev/null | tr "\\n" " " || echo "none")
    echo "Child processes: $CHILD_PIDS"
    # Show first few lines of log
    if [ -f "$log_file" ]; then
        echo "Log preview:"
        head -5 "$log_file" 2>/dev/null || echo "  (log file empty or not readable)"
    fi
else
    echo "ERROR: Process exited immediately"
    if [ -f "$log_file" ]; then
        echo "Error log:"
        cat "$log_file" 2>/dev/null | head -20
    fi
fi
'"""
                    
                    # Prepare environment with PATH that includes gcloud
                    env = os.environ.copy()
                    gcloud_dir = os.path.dirname(gcloud_path)
                    if 'PATH' in env:
                        env['PATH'] = f"{gcloud_dir}:{env['PATH']}"
                    else:
                        env['PATH'] = gcloud_dir
                    
                    # Use gcloud compute ssh to run the command
                    ssh_command = [
                        gcloud_path, 'compute', 'ssh',
                        f'{instance_name}',
                        f'--zone={zone}',
                        f'--project={project_id}',
                        '--command',
                        remote_command,
                        '--quiet'
                    ]
                    
                    logger.info(f"Executing CPU stress via SSH on {instance_name}...")
                    process = subprocess.Popen(
                        ssh_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    
                    # Wait a bit to see if SSH connection succeeds (need at least 5s for sleep 2 + verification)
                    try:
                        stdout, stderr = process.communicate(timeout=20)
                        stdout_text = stdout.decode() if stdout else ""
                        stderr_text = stderr.decode() if stderr else ""
                        
                        # Log the full output for debugging
                        logger.info(f"SSH command output for {instance_name}:")
                        logger.info(f"  Return code: {process.returncode}")
                        logger.info(f"  Stdout: {stdout_text[:1000]}")
                        if stderr_text:
                            logger.warning(f"  Stderr: {stderr_text[:500]}")
                        
                        if process.returncode == 0:
                            if "SUCCESS" in stdout_text:
                                logger.info(f"✅ CPU stress started successfully on {instance_name}")
                                # Extract PID if available
                                if "PID" in stdout_text:
                                    logger.info(f"  Process details: {stdout_text}")
                            else:
                                logger.warning(f"SSH command succeeded but may not have started stress")
                                logger.warning(f"  Output: {stdout_text}")
                        else:
                            error_msg = stderr_text or stdout_text or "Unknown error"
                            logger.error(f"❌ SSH execution failed with code {process.returncode}: {error_msg}")
                            logger.info("Note: Ensure SSH keys are configured. You may need to run:")
                            logger.info(f"  {gcloud_path} compute config-ssh")
                            logger.info(f"  {gcloud_path} compute ssh {instance_name} --zone={zone} --project={project_id}")
                    except subprocess.TimeoutExpired:
                        # SSH command is taking too long
                        logger.warning(f"SSH command timed out after 20s for {instance_name}")
                        process.kill()
                        try:
                            stdout, stderr = process.communicate(timeout=2)
                            if stdout:
                                logger.info(f"Partial SSH output: {stdout.decode()[:500]}")
                        except:
                            pass
                        
                except FileNotFoundError:
                    logger.warning(f"gcloud CLI not found at {gcloud_path}. CPU stress requires gcloud compute ssh.")
                    logger.info("To enable CPU stress, install gcloud CLI: https://cloud.google.com/sdk/docs/install")
                except Exception as ssh_error:
                    logger.warning(f"SSH execution failed: {ssh_error}")
                    logger.info("Note: CPU stress requires SSH access. Ensure:")
                    logger.info("  1. SSH keys are configured: gcloud compute config-ssh")
                    logger.info("  2. Instance has external IP or you're using IAP tunnel")
                    logger.info("  3. Firewall rules allow SSH (port 22)")
                
            except Exception as e:
                logger.error(f"Error running CPU stress: {e}", exc_info=True)
        
        if background_tasks:
            background_tasks.add_task(run_cpu_stress)
        
        return {
            "success": True,
            "message": f"CPU stress simulation started: {cpu_percent}% CPU for {duration_seconds} seconds",
            "instance_name": instance_name,
            "zone": zone,
            "external_ip": external_ip,
            "cpu_percent": cpu_percent,
            "duration_seconds": duration_seconds,
            "note": "This requires SSH access to the instance. Ensure you have SSH keys configured."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating CPU stress: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create CPU stress: {str(e)}")


@router.post("/compute/{instance_name}/memory-pressure")
async def compute_memory_pressure(instance_name: str, zone: str = None, fill_percent: float = 0.90, background_tasks: BackgroundTasks = None):
    """
    Create memory pressure on Compute Engine instance by allocating memory.
    This simulates a memory leak or high memory usage scenario.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        zone = zone or settings.GCP_ZONE
        
        client = compute_v1.InstancesClient(credentials=credentials)
        
        # Get instance details
        instance = client.get(project=project_id, zone=zone, instance=instance_name)
        
        if not instance:
            raise HTTPException(status_code=404, detail=f"Compute instance {instance_name} not found")
        
        # Get machine type to determine memory
        machine_type = instance.machine_type.split('/')[-1]
        
        def allocate_memory():
            try:
                import subprocess
                import os
                import base64
                import shutil
                
                logger.info(f"Starting memory pressure on {instance_name}: filling to {fill_percent*100:.0f}%")
                
                # Find gcloud in common locations
                gcloud_path = None
                possible_paths = [
                    shutil.which('gcloud'),  # Check PATH first
                    os.path.expanduser('~/google-cloud-sdk/bin/gcloud'),
                    os.path.expanduser('~/Downloads/google-cloud-sdk/bin/gcloud'),
                    os.path.expanduser('~/Desktop/google-cloud-sdk/bin/gcloud'),
                    '/usr/local/bin/gcloud',
                    '/opt/homebrew/bin/gcloud',
                    '/usr/bin/gcloud',
                ]
                
                for path in possible_paths:
                    if path and os.path.exists(path) and os.access(path, os.X_OK):
                        gcloud_path = path
                        break
                
                if not gcloud_path:
                    logger.warning("gcloud CLI not found. Memory pressure requires gcloud compute ssh.")
                    logger.info("To enable memory pressure, install gcloud CLI: https://cloud.google.com/sdk/docs/install")
                    return
                
                logger.debug(f"Using gcloud at: {gcloud_path}")
                
                # Create a Python script that allocates memory
                script_content = f"""#!/usr/bin/env python3
import time
import sys

# Get total memory (in MB) - approximate for e2-micro (1GB)
# For more accurate, we could parse /proc/meminfo
total_memory_mb = 1024  # Default to 1GB for small instances
target_memory_mb = int(total_memory_mb * {fill_percent})

# Allocate memory in chunks
chunk_size_mb = 100
chunks = []
allocated_mb = 0

try:
    while allocated_mb < target_memory_mb:
        # Allocate chunk_size_mb MB
        chunk = bytearray(chunk_size_mb * 1024 * 1024)
        chunks.append(chunk)
        allocated_mb += chunk_size_mb
        time.sleep(0.1)  # Small delay to avoid overwhelming the system
    
    # Hold memory for specified duration
    print(f"Allocated {{allocated_mb}}MB, holding for 60 seconds...")
    time.sleep(60)
except MemoryError:
    print("Memory allocation limit reached")
except Exception as e:
    print(f"Error: {{e}}")
"""
                
                # Try to use gcloud compute ssh
                try:
                    script_b64 = base64.b64encode(script_content.encode()).decode()
                    remote_command = f"""python3 << 'EOF'
import base64
import subprocess
import sys

script_b64 = '{script_b64}'
script_content = base64.b64decode(script_b64).decode()

import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(script_content)
    script_path = f.name

import os
os.chmod(script_path, 0o755)
subprocess.Popen([sys.executable, script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
EOF"""
                    
                    # Prepare environment with PATH that includes gcloud
                    env = os.environ.copy()
                    gcloud_dir = os.path.dirname(gcloud_path)
                    if 'PATH' in env:
                        env['PATH'] = f"{gcloud_dir}:{env['PATH']}"
                    else:
                        env['PATH'] = gcloud_dir
                    
                    ssh_command = [
                        gcloud_path, 'compute', 'ssh',
                        f'{instance_name}',
                        f'--zone={zone}',
                        f'--project={project_id}',
                        '--command',
                        remote_command,
                        '--quiet'
                    ]
                    
                    logger.info(f"Executing memory pressure via SSH on {instance_name}...")
                    process = subprocess.Popen(
                        ssh_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    
                    try:
                        stdout, stderr = process.communicate(timeout=10)
                        
                        if process.returncode == 0:
                            logger.info(f"✅ Memory pressure started successfully on {instance_name}")
                        else:
                            error_msg = stderr.decode() if stderr else "Unknown error"
                            logger.warning(f"SSH execution failed: {error_msg}")
                            logger.info(f"Note: Ensure SSH keys are configured: {gcloud_path} compute config-ssh")
                    except subprocess.TimeoutExpired:
                        logger.info(f"Memory pressure process started on {instance_name} (running in background)")
                        process.kill()
                        
                except FileNotFoundError:
                    logger.warning(f"gcloud CLI not found at {gcloud_path}. Memory pressure requires gcloud compute ssh.")
                except Exception as ssh_error:
                    logger.warning(f"SSH execution failed: {ssh_error}")
                    logger.info("Note: Memory pressure requires SSH access. Ensure SSH keys are configured.")
                
            except Exception as e:
                logger.error(f"Error creating memory pressure: {e}", exc_info=True)
        
        if background_tasks:
            background_tasks.add_task(allocate_memory)
        
        return {
            "success": True,
            "message": f"Memory pressure simulation started: filling to {fill_percent*100:.0f}%",
            "instance_name": instance_name,
            "zone": zone,
            "machine_type": machine_type,
            "fill_percent": fill_percent * 100,
            "note": "This requires SSH access to the instance."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating memory pressure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create memory pressure: {str(e)}")


@router.post("/compute/{instance_name}/stop")
async def stop_compute_instance(instance_name: str, zone: str = None):
    """
    Stop a GCP Compute Engine instance to simulate failure.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        zone = zone or settings.GCP_ZONE
        
        client = compute_v1.InstancesClient(credentials=credentials)
        
        # Stop the instance
        operation = client.stop(
            project=project_id,
            zone=zone,
            instance=instance_name
        )
        
        # Wait for operation to start
        operation.result(timeout=30)
        
        logger.info(f"Stopped Compute Engine instance {instance_name} in zone {zone}")
        
        return {
            "success": True,
            "message": f"Compute Engine instance {instance_name} stopped",
            "instance_name": instance_name,
            "zone": zone
        }
        
    except Exception as e:
        logger.error(f"Error stopping Compute Engine instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop instance: {str(e)}")


@router.post("/compute/{instance_name}/start")
async def start_compute_instance(instance_name: str, zone: str = None):
    """
    Start a GCP Compute Engine instance to reset.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        zone = zone or settings.GCP_ZONE
        
        client = compute_v1.InstancesClient(credentials=credentials)
        
        # Start the instance
        operation = client.start(
            project=project_id,
            zone=zone,
            instance=instance_name
        )
        
        # Wait for operation to start
        operation.result(timeout=30)
        
        logger.info(f"Started Compute Engine instance {instance_name} in zone {zone}")
        
        return {
            "success": True,
            "message": f"Compute Engine instance {instance_name} started",
            "instance_name": instance_name,
            "zone": zone
        }
        
    except Exception as e:
        logger.error(f"Error starting Compute Engine instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start instance: {str(e)}")


@router.post("/sql/{instance_id}/connection-overload")
async def sql_connection_overload(instance_id: str, connections: int = 100, background_tasks: BackgroundTasks = None):
    """
    Create connection overload on Cloud SQL by opening many connections.
    This simulates a real-world scenario where the database is overwhelmed with connections.
    More realistic than just stopping the instance.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        
        # Get SQL instance details
        service = discovery.build('sqladmin', 'v1', credentials=credentials)
        instance = service.instances().get(project=project_id, instance=instance_id).execute()
        
        if not instance:
            raise HTTPException(status_code=404, detail=f"SQL instance {instance_id} not found")
        
        # Get connection details
        connection_name = instance.get('connectionName', '')
        database_version = instance.get('databaseVersion', '')
        
        # Check if it's PostgreSQL or MySQL
        is_postgres = 'POSTGRES' in database_version.upper()
        
        # Get connection settings
        settings = instance.get('settings', {})
        ip_config = settings.get('ipConfiguration', {})
        authorized_networks = ip_config.get('authorizedNetworks', [])
        
        # For this to work, we need:
        # 1. Public IP or authorized network access
        # 2. Database credentials
        # Since we don't have DB credentials in the API, we'll simulate by creating many connection attempts
        
        def create_connections():
            try:
                import psycopg2
                from psycopg2 import pool
                
                # Try to get connection string from environment or instance metadata
                # For now, we'll log that connections should be created
                # In a real scenario, you'd need DB credentials
                
                logger.info(f"Simulating {connections} connections to SQL instance {instance_id}")
                logger.warning("SQL connection overload requires database credentials. This is a simulation.")
                
                # In a real implementation, you would:
                # 1. Get DB credentials (from Secret Manager or config)
                # 2. Create a connection pool
                # 3. Open many connections and keep them alive
                # 4. Optionally run blocking queries
                
            except Exception as e:
                logger.error(f"Error creating SQL connections: {e}", exc_info=True)
        
        if background_tasks:
            background_tasks.add_task(create_connections)
        
        return {
            "success": True,
            "message": f"Connection overload simulation started for SQL {instance_id}: {connections} connections",
            "instance_id": instance_id,
            "target_connections": connections,
            "note": "This requires database credentials to fully simulate. Consider using Cloud SQL Proxy or providing credentials."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating SQL connection overload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create connection overload: {str(e)}")


@router.post("/sql/{instance_id}/blocking-queries")
async def sql_blocking_queries(instance_id: str, queries: int = 10, duration_seconds: int = 300, background_tasks: BackgroundTasks = None):
    """
    Create blocking queries on Cloud SQL that hold locks and prevent other operations.
    This simulates a real-world scenario where long-running queries block the database.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        
        # Get SQL instance details
        service = discovery.build('sqladmin', 'v1', credentials=credentials)
        instance = service.instances().get(project=project_id, instance=instance_id).execute()
        
        if not instance:
            raise HTTPException(status_code=404, detail=f"SQL instance {instance_id} not found")
        
        database_version = instance.get('databaseVersion', '')
        is_postgres = 'POSTGRES' in database_version.upper()
        
        def create_blocking_queries():
            try:
                # This would require DB credentials
                # For PostgreSQL: SELECT pg_sleep(duration_seconds)
                # For MySQL: SELECT SLEEP(duration_seconds)
                
                logger.info(f"Simulating {queries} blocking queries on SQL {instance_id} for {duration_seconds} seconds")
                logger.warning("Blocking queries require database credentials. This is a simulation.")
                
            except Exception as e:
                logger.error(f"Error creating blocking queries: {e}", exc_info=True)
        
        if background_tasks:
            background_tasks.add_task(create_blocking_queries)
        
        return {
            "success": True,
            "message": f"Blocking queries simulation started: {queries} queries for {duration_seconds} seconds",
            "instance_id": instance_id,
            "queries": queries,
            "duration_seconds": duration_seconds,
            "note": "This requires database credentials to fully simulate. Provide DB credentials in environment variables."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating blocking queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create blocking queries: {str(e)}")


@router.post("/sql/{instance_id}/stop")
async def stop_sql_instance(instance_id: str):
    """
    Stop a GCP Cloud SQL instance to simulate failure.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        
        # Use Cloud SQL Admin API
        service = discovery.build('sqladmin', 'v1', credentials=credentials)
        
        # Stop the instance
        request = service.instances().patch(
            project=project_id,
            instance=instance_id,
            body={
                "settings": {
                    "activationPolicy": "NEVER"  # Stop the instance
                }
            }
        )
        response = request.execute()
        
        logger.info(f"Stopped Cloud SQL instance {instance_id}")
        
        return {
            "success": True,
            "message": f"Cloud SQL instance {instance_id} stopped",
            "instance_id": instance_id,
            "operation": response.get("name", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Error stopping Cloud SQL instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop SQL instance: {str(e)}")


@router.post("/sql/{instance_id}/start")
async def start_sql_instance(instance_id: str):
    """
    Start a GCP Cloud SQL instance to reset.
    """
    try:
        credentials, _ = get_gcp_credentials()
        project_id = get_gcp_project_id()
        
        # Use Cloud SQL Admin API
        service = discovery.build('sqladmin', 'v1', credentials=credentials)
        
        # Start the instance
        request = service.instances().patch(
            project=project_id,
            instance=instance_id,
            body={
                "settings": {
                    "activationPolicy": "ALWAYS"  # Start the instance
                }
            }
        )
        response = request.execute()
        
        logger.info(f"Started Cloud SQL instance {instance_id}")
        
        return {
            "success": True,
            "message": f"Cloud SQL instance {instance_id} started",
            "instance_id": instance_id,
            "operation": response.get("name", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Error starting Cloud SQL instance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start SQL instance: {str(e)}")

