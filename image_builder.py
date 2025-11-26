"""Docker image building utilities.

This module provides functions to build Docker images from Dockerfiles
and extract build information like image size and build time.
"""

import os
import shutil
import subprocess
import time
from typing import Dict, Optional, Any


class DockerUnavailableError(RuntimeError):
    """Raised when Docker CLI is not available."""


def _ensure_docker_available() -> None:
    """Check if Docker CLI is available."""
    if shutil.which("docker") is None:
        raise DockerUnavailableError(
            "Docker CLI not found in PATH. Install Docker or ensure it is accessible."
        )


def _run_docker_command(args: list, timeout: int = 600) -> tuple[str, str, int]:
    """Run a Docker command and return output.
    
    Args:
        args: Docker command arguments
        timeout: Command timeout in seconds
        
    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    _ensure_docker_available()
    try:
        result = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        raise DockerUnavailableError("Docker CLI could not be executed")
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout} seconds", -1


def _get_image_size(image_tag: str) -> Optional[int]:
    """Get image size in bytes.
    
    Args:
        image_tag: Docker image tag
        
    Returns:
        Image size in bytes, or None if not found
    """
    stdout, stderr, returncode = _run_docker_command([
        "inspect", image_tag, "--format", "{{.Size}}"
    ])
    
    if returncode == 0 and stdout.strip():
        try:
            return int(stdout.strip())
        except ValueError:
            pass
    return None


def build_image_from_dockerfile(
    dockerfile_path: str,
    image_tag: str,
    build_context: Optional[str] = None,
    timeout: int = 600
) -> Dict[str, Any]:
    """Build a Docker image from a Dockerfile.
    
    Args:
        dockerfile_path: Path to Dockerfile
        image_tag: Tag to assign to the built image
        build_context: Build context directory (defaults to Dockerfile directory)
        timeout: Build timeout in seconds
        
    Returns:
        Dictionary with build results:
        - success: Whether build succeeded
        - image_tag: Image tag used
        - build_time: Build time in seconds
        - image_size_bytes: Image size in bytes (if available)
        - build_output: Build output text
        - error: Error message if failed
    """
    if build_context is None:
        build_context = os.path.dirname(dockerfile_path) or "."
    
    if not os.path.exists(dockerfile_path):
        return {
            "success": False,
            "error": f"Dockerfile not found: {dockerfile_path}",
            "image_tag": image_tag,
            "build_time": 0,
            "image_size_bytes": None,
            "build_output": ""
        }
    
    start_time = time.time()
    
    stdout, stderr, returncode = _run_docker_command([
        "build",
        "-f", dockerfile_path,
        "-t", image_tag,
        build_context
    ], timeout=timeout)
    
    build_time = time.time() - start_time
    
    result = {
        "success": returncode == 0,
        "image_tag": image_tag,
        "build_time": round(build_time, 2),
        "image_size_bytes": None,
        "build_output": stdout + stderr,
        "error": None
    }
    
    if returncode != 0:
        result["error"] = stderr or "Build failed with unknown error"
    else:
        # Try to get image size
        image_size = _get_image_size(image_tag)
        if image_size:
            result["image_size_bytes"] = image_size
    
    return result


def image_exists(image_tag: str) -> bool:
    """Check if a Docker image exists.
    
    Args:
        image_tag: Docker image tag to check
        
    Returns:
        True if image exists, False otherwise
    """
    stdout, stderr, returncode = _run_docker_command([
        "images", "-q", image_tag
    ])
    return returncode == 0 and bool(stdout.strip())


def remove_image(image_tag: str) -> bool:
    """Remove a Docker image.
    
    Args:
        image_tag: Docker image tag to remove
        
    Returns:
        True if removal succeeded, False otherwise
    """
    stdout, stderr, returncode = _run_docker_command([
        "rmi", "-f", image_tag
    ])
    return returncode == 0

