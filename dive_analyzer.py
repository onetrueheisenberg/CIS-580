import os
import shutil
import subprocess
import re
from typing import Dict, Optional, Any


class DiveUnavailableError(RuntimeError):
    """Raised when dive CLI is not available."""


def _ensure_dive_available() -> None:
    """Check if dive CLI is available."""
    if shutil.which("dive") is None:
        raise DiveUnavailableError(
            "dive CLI not found in PATH. Install dive: https://github.com/wagoodman/dive"
        )


def _parse_dive_output(output: str) -> Dict[str, Any]:
    """Parse dive text output to extract metrics.
    
    Args:
        output: Text output from dive command
        
    Returns:
        Dictionary with parsed metrics
    """
    result = {
        "efficiency": None,
        "wasted_bytes": None,
        "wasted_percent": None,
        "user_wasted_percent": None,
        "total_size": None,
        "layer_count": 0,
        "raw_output": output
    }
    
    # Try new format first (JSON-like): "efficiency: 99.5332 %"
    efficiency_match = re.search(r'efficiency:\s*([\d.]+)\s*%', output, re.IGNORECASE)
    if efficiency_match:
        result["efficiency"] = float(efficiency_match.group(1))
    else:
        # Try old format: "efficiency: 85.2%"
        efficiency_match = re.search(r'efficiency:\s*([\d.]+)%', output, re.IGNORECASE)
        if efficiency_match:
            result["efficiency"] = float(efficiency_match.group(1))
    
    # Try new format: "wastedBytes: 3530062 bytes (3.5 MB)"
    wasted_bytes_match = re.search(r'wastedBytes:\s*(\d+)\s*bytes', output, re.IGNORECASE)
    if wasted_bytes_match:
        result["wasted_bytes"] = int(wasted_bytes_match.group(1))
    else:
        # Try old format: "wasted space: 3.5 MB"
        wasted_bytes_match = re.search(r'wasted space:\s*([\d.]+)\s*([KMGT]?B)', output, re.IGNORECASE)
        if wasted_bytes_match:
            value = float(wasted_bytes_match.group(1))
            unit = wasted_bytes_match.group(2).upper() if wasted_bytes_match.group(2) else "B"
            multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
            result["wasted_bytes"] = int(value * multipliers.get(unit, 1))
    
    # Calculate wasted_percent from wasted_bytes and total_size if available
    if result["wasted_bytes"] and result.get("total_size"):
        result["wasted_percent"] = (result["wasted_bytes"] / result["total_size"]) * 100
    
    # Try new format: "userWastedPercent: 1.3874 %"
    user_wasted_match = re.search(r'userWastedPercent:\s*([\d.]+)\s*%', output, re.IGNORECASE)
    if user_wasted_match:
        result["user_wasted_percent"] = float(user_wasted_match.group(1))
    else:
        # Try old format: "user wasted: 1.4%"
        user_wasted_match = re.search(r'user wasted:\s*([\d.]+)%', output, re.IGNORECASE)
        if user_wasted_match:
            result["user_wasted_percent"] = float(user_wasted_match.group(1))
    
    # Try to find total size from image analysis
    # Look for "Total Image size:" or similar patterns
    total_size_match = re.search(r'total size:\s*([\d.]+)\s*([KMGT]?B)', output, re.IGNORECASE)
    if total_size_match:
        value = float(total_size_match.group(1))
        unit = total_size_match.group(2).upper() if total_size_match.group(2) else "B"
        multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        result["total_size"] = int(value * multipliers.get(unit, 1))
    else:
        # Try to extract from "Image Source:" or image metadata
        # If we have wasted_bytes and efficiency, we can estimate total_size
        if result["wasted_bytes"] and result["efficiency"]:
            # wasted_bytes = total_size * (1 - efficiency/100)
            # total_size = wasted_bytes / (1 - efficiency/100)
            if result["efficiency"] < 100:
                result["total_size"] = int(result["wasted_bytes"] / (1 - result["efficiency"] / 100))
    
    # Count layers - look for layer indicators in the output
    layer_count = len(re.findall(r'(?:Step|Layer)\s+\d+', output, re.IGNORECASE))
    if layer_count == 0:
        # Try counting from inefficient files section or other indicators
        layer_indicators = re.findall(r'Layer\s+\d+|Step\s+\d+', output, re.IGNORECASE)
        layer_count = len(set(layer_indicators)) if layer_indicators else 0
    
    result["layer_count"] = layer_count if layer_count > 0 else 0
    
    return result


def analyze_image_with_dive(image_name: str) -> Dict[str, Any]:
    """Analyze a Docker image using dive.
    
    Args:
        image_name: Docker image name/tag to analyze
        
    Returns:
        Dictionary with analysis results including:
        - efficiency: Efficiency percentage (0-100)
        - wasted_bytes: Wasted space in bytes
        - wasted_percent: Wasted space as percentage
        - user_wasted_percent: User wasted space percentage
        - total_size: Total image size in bytes
        - layer_count: Number of layers
        - success: Whether analysis succeeded
        - error: Error message if failed
    """
    _ensure_dive_available()
    
    try:
        env = os.environ.copy()
        env["CI"] = "true"
        
        result = subprocess.run(
            ["dive", image_name],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
            check=False
        )
        
        if result.returncode != 0:
            output = result.stdout + result.stderr
            parsed = _parse_dive_output(output)
            parsed["success"] = False
            parsed["error"] = f"dive exited with code {result.returncode}"
            return parsed
        
        parsed = _parse_dive_output(result.stdout)
        parsed["success"] = True
        return parsed
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "dive analysis timed out after 5 minutes",
            "efficiency": None,
            "wasted_bytes": None,
            "wasted_percent": None,
            "user_wasted_percent": None,
            "total_size": None,
            "layer_count": 0
        }
    except FileNotFoundError:
        raise DiveUnavailableError("dive CLI could not be executed")
    except Exception as e:
        return {
            "success": False,
            "error": f"dive analysis failed: {str(e)}",
            "efficiency": None,
            "wasted_bytes": None,
            "wasted_percent": None,
            "user_wasted_percent": None,
            "total_size": None,
            "layer_count": 0
        }


def compare_images_with_dive(original_image: str, optimized_image: str) -> Dict[str, Any]:
    """Compare two Docker images using dive analysis.
    
    Args:
        original_image: Name/tag of original image
        optimized_image: Name/tag of optimized image
        
    Returns:
        Dictionary with comparison results including:
        - original: Dive analysis of original image
        - optimized: Dive analysis of optimized image
        - efficiency_improvement: Change in efficiency percentage
        - wasted_space_reduction: Reduction in wasted space (bytes)
        - wasted_space_reduction_percent: Reduction in wasted space (%)
        - size_reduction: Reduction in total size (bytes)
        - size_reduction_percent: Reduction in total size (%)
    """
    original_analysis = analyze_image_with_dive(original_image)
    optimized_analysis = analyze_image_with_dive(optimized_image)
    
    comparison = {
        "original": original_analysis,
        "optimized": optimized_analysis,
        "efficiency_improvement": None,
        "wasted_space_reduction": None,
        "wasted_space_reduction_percent": None,
        "size_reduction": None,
        "size_reduction_percent": None
    }
    
    if (original_analysis.get("efficiency") is not None and 
        optimized_analysis.get("efficiency") is not None):
        comparison["efficiency_improvement"] = (
            optimized_analysis["efficiency"] - original_analysis["efficiency"]
        )
    
    if (original_analysis.get("wasted_bytes") is not None and 
        optimized_analysis.get("wasted_bytes") is not None):
        comparison["wasted_space_reduction"] = (
            original_analysis["wasted_bytes"] - optimized_analysis["wasted_bytes"]
        )
        if original_analysis["wasted_bytes"] > 0:
            comparison["wasted_space_reduction_percent"] = (
                (comparison["wasted_space_reduction"] / original_analysis["wasted_bytes"]) * 100
            )
    
    if (original_analysis.get("total_size") is not None and 
        optimized_analysis.get("total_size") is not None):
        comparison["size_reduction"] = (
            original_analysis["total_size"] - optimized_analysis["total_size"]
        )
        if original_analysis["total_size"] > 0:
            comparison["size_reduction_percent"] = (
                (comparison["size_reduction"] / original_analysis["total_size"]) * 100
            )
    
    return comparison

