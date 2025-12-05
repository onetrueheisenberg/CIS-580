import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


HISTORY_FILE = "analysis_history.json"


def get_history_file_path() -> Path:
    """Get the path to the history file.
    
    Returns:
        Path to history JSON file
    """
    return Path(__file__).parent / HISTORY_FILE


def load_history() -> List[Dict[str, Any]]:
    """Load analysis history from disk.
    
    Returns:
        List of historical run records, sorted by timestamp (newest first)
    """
    history_file = get_history_file_path()
    
    if not history_file.exists():
        return []
    
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return history
    except Exception as e:
        print(f"Error loading history: {e}")
        return []


def save_history(history: List[Dict[str, Any]]) -> None:
    """Save analysis history to disk.
    
    Args:
        history: List of historical run records
    """
    history_file = get_history_file_path()
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving history: {e}")


def add_run_to_history(
    results: List[Dict[str, Any]],
    repos_file: str,
    model: str,
    skip_test: bool,
    max_repos: Optional[int] = None
) -> Dict[str, Any]:
    """Add a batch run to history.
    
    Args:
        results: List of analysis results from the batch run
        repos_file: Path to repositories file used
        model: Model used for analysis
        skip_test: Whether test stage was skipped
        max_repos: Maximum number of repos processed
        
    Returns:
        History record dictionary
    """
    from results_manager import get_results_summary
    
    summary = get_results_summary(results)
    timestamp = datetime.now().isoformat()
    
    # Count successes and failures
    successful = [r for r in results if r.get("success", False)]
    failed = [r for r in results if not r.get("success", False)]
    
    history_record = {
        "timestamp": timestamp,
        "repos_file": repos_file,
        "model": model,
        "skip_test": skip_test,
        "max_repos": max_repos,
        "total_repos": len(results),
        "successful_repos": len(successful),
        "failed_repos": len(failed),
        "summary": summary,
        "results_file": f"batch_results_{timestamp.replace(':', '-').replace('.', '-')}.json"
    }
    
    # Save results to a timestamped file
    results_file_path = Path(__file__).parent / history_record["results_file"]
    try:
        with open(results_file_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving results file: {e}")
        history_record["results_file"] = None
    
    # Add to history
    history = load_history()
    history.append(history_record)
    save_history(history)
    
    return history_record


def get_history_record(timestamp: str) -> Optional[Dict[str, Any]]:
    """Get a specific history record by timestamp.
    
    Args:
        timestamp: ISO timestamp of the run
        
    Returns:
        History record if found, None otherwise
    """
    history = load_history()
    for record in history:
        if record.get("timestamp") == timestamp:
            return record
    return None


def load_results_from_history(timestamp: str) -> Optional[List[Dict[str, Any]]]:
    """Load results for a specific historical run.
    
    Args:
        timestamp: ISO timestamp of the run
        
    Returns:
        List of results if found, None otherwise
    """
    record = get_history_record(timestamp)
    if not record or not record.get("results_file"):
        return None
    
    results_file = Path(__file__).parent / record["results_file"]
    if not results_file.exists():
        return None
    
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading results from history: {e}")
        return None


def delete_history_record(timestamp: str) -> bool:
    """Delete a history record and its associated results file.
    
    Args:
        timestamp: ISO timestamp of the run to delete
        
    Returns:
        True if deleted successfully, False otherwise
    """
    history = load_history()
    record = get_history_record(timestamp)
    
    if not record:
        return False
    
    # Delete results file if it exists
    if record.get("results_file"):
        results_file = Path(__file__).parent / record["results_file"]
        if results_file.exists():
            try:
                results_file.unlink()
            except Exception as e:
                print(f"Error deleting results file: {e}")
    
    # Remove from history
    history = [h for h in history if h.get("timestamp") != timestamp]
    save_history(history)
    
    return True


def get_history_summary() -> Dict[str, Any]:
    """Get summary statistics across all history.
    
    Returns:
        Dictionary with summary statistics
    """
    history = load_history()
    
    if not history:
        return {
            "total_runs": 0,
            "total_repos_processed": 0,
            "total_successful_repos": 0,
            "total_failed_repos": 0,
            "total_space_saved_mb": 0,
            "avg_size_reduction_percent": 0
        }
    
    total_runs = len(history)
    total_repos = sum(h.get("total_repos", 0) for h in history)
    total_successful = sum(h.get("successful_repos", 0) for h in history)
    total_failed = sum(h.get("failed_repos", 0) for h in history)
    
    # Calculate total space saved
    total_space_saved = 0
    size_reductions = []
    
    for record in history:
        summary = record.get("summary", {})
        total_space_saved += summary.get("total_size_saved_bytes", 0)
        avg_reduction = summary.get("avg_size_reduction_percent", 0)
        if avg_reduction > 0:
            size_reductions.append(avg_reduction)
    
    total_space_saved_mb = total_space_saved / (1024 * 1024) if total_space_saved else 0
    avg_size_reduction = sum(size_reductions) / len(size_reductions) if size_reductions else 0
    
    return {
        "total_runs": total_runs,
        "total_repos_processed": total_repos,
        "total_successful_repos": total_successful,
        "total_failed_repos": total_failed,
        "total_space_saved_mb": round(total_space_saved_mb, 2),
        "avg_size_reduction_percent": round(avg_size_reduction, 2)
    }

