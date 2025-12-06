"""Helper utilities for Docker operations using subprocess as fallback."""
import subprocess
import json
from typing import List, Dict, Any, Optional
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def get_containers_via_cli() -> List[Dict[str, Any]]:
    """Get containers using Docker CLI as fallback."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    container_data = json.loads(line)
                    containers.append({
                        "id": container_data.get("ID", ""),
                        "name": container_data.get("Names", ""),
                        "image": container_data.get("Image", ""),
                        "status": container_data.get("Status", ""),
                        "ports": container_data.get("Ports", "")
                    })
                except json.JSONDecodeError:
                    continue
        
        return containers
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get containers via CLI: {e}")
        return []
    except FileNotFoundError:
        logger.error("Docker CLI not found")
        return []


def get_container_stats_via_cli(container_name: str) -> Optional[Dict[str, Any]]:
    """Get container stats using Docker CLI."""
    try:
        result = subprocess.run(
            ["docker", "stats", container_name, "--no-stream", "--format", "json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        
        if result.stdout.strip():
            return json.loads(result.stdout.strip())
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        logger.debug(f"Failed to get stats for {container_name}: {e}")
        return None


def get_container_logs_via_cli(container_name: str, tail: int = 100) -> List[str]:
    """Get container logs using Docker CLI."""
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(tail), container_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        
        return result.stdout.strip().split('\n')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.debug(f"Failed to get logs for {container_name}: {e}")
        return []


def restart_container_via_cli(container_name: str) -> bool:
    """Restart container using Docker CLI."""
    try:
        subprocess.run(
            ["docker", "restart", container_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error(f"Failed to restart {container_name}: {e}")
        return False

