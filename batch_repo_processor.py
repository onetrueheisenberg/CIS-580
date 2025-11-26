"""Batch repository processor for Docker analysis.

This module processes multiple repositories, builds original and optimized
Docker images, and runs comprehensive analysis on them.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from llm_agents.dockerfile_pipeline import (
    DockerfilePipeline,
    get_all_repos_from_file,
    clone_repo,
    delete_repo
)
from llm_agents.dockerfile_llm_analyzer import find_dockerfiles
from docker_image_analyzer import list_images, analyze_image, compare_images
from dive_analyzer import analyze_image_with_dive, compare_images_with_dive
from image_builder import build_image_from_dockerfile, image_exists, remove_image
from rate_limiter import get_rate_limiter, reset_rate_limiter


def sanitize_repo_name(repo_url: str) -> str:
    """Convert repo URL to a valid Docker image name.
    
    Args:
        repo_url: Repository URL (e.g., https://github.com/user/repo)
        
    Returns:
        Sanitized name suitable for Docker image tag
    """
    repo_name = repo_url.rstrip("/").split("/")[-1]
    repo_name = repo_name.replace(".", "-").replace("_", "-").lower()
    return repo_name


def estimate_improvements_from_llm(llm_results: Dict[str, Any]) -> Dict[str, Any]:
    estimation = {
        "estimated": True,
        "size_reduction_bytes": None,
        "size_reduction_percent": None,
        "efficiency_improvement": None,
        "wasted_space_reduction_bytes": None,
        "wasted_space_reduction_percent": None
    }
    
    if not llm_results.get("success"):
        return estimation
    
    original_analysis = llm_results.get("original_analysis", {})
    validation_stage = llm_results.get("stages", {}).get("validation", {})
    optimized_analysis = validation_stage.get("result", {}) if validation_stage.get("success") else {}
    
    orig_scores = original_analysis.get("scores", {})
    opt_scores = optimized_analysis.get("scores", {})
    
    orig_wasted_kb = orig_scores.get("estimated_wasted_space_kb", 0)
    opt_wasted_kb = opt_scores.get("estimated_wasted_space_kb", 0)
    
    if orig_wasted_kb > 0:
        wasted_reduction_kb = orig_wasted_kb - opt_wasted_kb
        estimation["wasted_space_reduction_bytes"] = int(wasted_reduction_kb * 1024)
        estimation["wasted_space_reduction_percent"] = round((wasted_reduction_kb / orig_wasted_kb) * 100, 2)
    
    # Estimate size reduction based on efficiency score improvement
    orig_efficiency = orig_scores.get("efficiency_score", 50)
    opt_efficiency = opt_scores.get("efficiency_score", 50)
    efficiency_improvement = opt_efficiency - orig_efficiency
    
    if efficiency_improvement > 0:
        estimation["efficiency_improvement"] = round(efficiency_improvement, 2)
        estimated_size_reduction_pct = efficiency_improvement * 0.5
        estimation["size_reduction_percent"] = round(estimated_size_reduction_pct, 2)
    
    orig_issues = len(original_analysis.get("security_risks", [])) + \
                  len(original_analysis.get("performance_issues", [])) + \
                  len(original_analysis.get("best_practices_missing", []))
    
    opt_issues = len(optimized_analysis.get("security_risks", [])) + \
                 len(optimized_analysis.get("performance_issues", [])) + \
                 len(optimized_analysis.get("best_practices_missing", []))
    
    issues_fixed = orig_issues - opt_issues
    if issues_fixed > 0:
        estimated_bytes_per_issue = 2 * 1024 * 1024
        estimated_size_reduction = issues_fixed * estimated_bytes_per_issue
        if estimation["size_reduction_bytes"] is None:
            estimation["size_reduction_bytes"] = estimated_size_reduction
        else:
            estimation["size_reduction_bytes"] += estimated_size_reduction
    
    return estimation


def process_single_repo(
    repo_url: str,
    pipeline: DockerfilePipeline,
    repos_dir: str,
    skip_test: bool = False,
    cleanup_repo: bool = True,
    cleanup_images: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """Process a single repository through the full analysis pipeline.
    
    Args:
        repo_url: Repository URL to process
        pipeline: DockerfilePipeline instance
        repos_dir: Directory to clone repositories into
        skip_test: Whether to skip Docker build/test stage
        cleanup_repo: Whether to cleanup cloned repo after processing
        cleanup_images: Whether to cleanup Docker images after processing
        progress_callback: Optional callback function for progress updates
        
    Returns:
        Dictionary with analysis results for the repository
    """
    result = {
        "repo_url": repo_url,
        "repo_name": sanitize_repo_name(repo_url),
        "success": False,
        "error": None,
        "original_image": {},
        "optimized_image": {},
        "dynamic_analysis": {},
        "comparison": {}
    }
    
    repo_name = result["repo_name"]
    original_tag = f"{repo_name}:original"
    optimized_tag = f"{repo_name}:optimized"
    
    try:
        if progress_callback:
            progress_callback(f"Cloning {repo_url}...")
        
        repo_path = clone_repo(repo_url, repos_dir)
        
        try:
            if progress_callback:
                progress_callback(f"Finding Dockerfiles in {repo_name}...")
            
            dockerfiles = find_dockerfiles(repo_path)
            if not dockerfiles:
                result["error"] = f"No Dockerfiles found in {repo_path}"
                return result
            
            dockerfile_path = dockerfiles[0]
            
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                original_dockerfile_content = f.read()
            
            if progress_callback:
                progress_callback(f"Building original image for {repo_name}...")
            
            build_context = os.path.dirname(dockerfile_path) or repo_path
            original_build = build_image_from_dockerfile(
                dockerfile_path,
                original_tag,
                build_context,
                timeout=600
            )
            
            original_build_success = bool(original_build.get("success"))
            result["original_image"]["tag"] = original_tag
            result["original_image"]["build_success"] = original_build_success
            result["original_image"]["build_output"] = original_build.get("output", "")
            result["original_image"]["build_errors"] = original_build.get("errors", "")
            result["original_image"]["size_bytes"] = original_build.get("image_size_bytes")
            result["original_image"]["build_time"] = original_build.get("build_time")
            
            if not original_build_success:
                result["error"] = f"Failed to build original image: {original_build.get('error') or original_build.get('errors')}"
                result["build_status"] = "original_build_failed"
            
            if progress_callback:
                progress_callback(f"Running LLM optimization for {repo_name}...")
            
            llm_results = pipeline.optimize_dockerfile(dockerfile_path, skip_test=skip_test)
            result["dynamic_analysis"]["llm_pipeline_results"] = llm_results
            
            if not llm_results.get("success"):
                result["error"] = "LLM pipeline failed"
                result["build_status"] = "llm_failed"
                return result
            
            optimized_dockerfile_content = llm_results.get("fixed_dockerfile", original_dockerfile_content)
            
            temp_dockerfile_path = os.path.join(repo_path, "Dockerfile.optimized")
            with open(temp_dockerfile_path, "w", encoding="utf-8") as f:
                f.write(optimized_dockerfile_content)
            
            if progress_callback:
                progress_callback(f"Building optimized image for {repo_name}...")
            
            optimized_build = build_image_from_dockerfile(
                temp_dockerfile_path,
                optimized_tag,
                build_context,
                timeout=600
            )
            
            optimized_build_success = bool(optimized_build.get("success"))
            result["optimized_image"]["tag"] = optimized_tag
            result["optimized_image"]["build_success"] = optimized_build_success
            result["optimized_image"]["build_output"] = optimized_build.get("output", "")
            result["optimized_image"]["build_errors"] = optimized_build.get("errors", "")
            result["optimized_image"]["size_bytes"] = optimized_build.get("image_size_bytes")
            result["optimized_image"]["build_time"] = optimized_build.get("build_time")
            
            if original_build_success and optimized_build_success:
                result["build_status"] = "success"
            elif not original_build_success:
                result["build_status"] = "original_build_failed"
            elif not optimized_build_success:
                result["build_status"] = "optimized_build_failed"
                result["error"] = f"Failed to build optimized image: {optimized_build.get('error') or optimized_build.get('errors')}"
            
            if result["build_status"] != "success":
                if progress_callback:
                    progress_callback(f"Estimating improvements for {repo_name} (build failed, using LLM analysis)...")
                
                estimation = estimate_improvements_from_llm(llm_results)
                result["comparison"]["estimation"] = estimation
                result["comparison"]["estimated"] = True
                result["estimated"] = True
                result["success"] = True
            
            if original_build_success and optimized_build_success:
                if progress_callback:
                    progress_callback(f"Running static analysis for {repo_name}...")
                
                images = list_images()
                original_image_dict = None
                optimized_image_dict = None
                
                for img in images:
                    repo_tag = img.get("Repository") or img.get("RepositoryName", "")
                    tag = img.get("Tag") or img.get("TagName", "")
                    if f"{repo_tag}:{tag}" == original_tag or tag == original_tag:
                        original_image_dict = img
                    if f"{repo_tag}:{tag}" == optimized_tag or tag == optimized_tag:
                        optimized_image_dict = img
                
                if original_image_dict and optimized_image_dict:
                    original_recs = analyze_image(original_image_dict)
                    optimized_recs = analyze_image(optimized_image_dict)
                    static_comparison = compare_images(original_image_dict, optimized_image_dict)
                    
                    result["original_image"]["static_analysis"] = [
                        {"severity": r.severity, "message": r.message}
                        for r in original_recs
                    ]
                    result["optimized_image"]["static_analysis"] = [
                        {"severity": r.severity, "message": r.message}
                        for r in optimized_recs
                    ]
                    result["comparison"]["static_analysis"] = static_comparison
                
                if progress_callback:
                    progress_callback(f"Running dive analysis for {repo_name}...")
                
                try:
                    original_dive = analyze_image_with_dive(original_tag)
                    optimized_dive = analyze_image_with_dive(optimized_tag)
                    dive_comparison = compare_images_with_dive(original_tag, optimized_tag)
                    
                    result["original_image"]["dive_analysis"] = original_dive
                    result["optimized_image"]["dive_analysis"] = optimized_dive
                    result["comparison"]["dive_analysis"] = dive_comparison
                except Exception as e:
                    result["original_image"]["dive_analysis"] = {"success": False, "error": str(e)}
                    result["optimized_image"]["dive_analysis"] = {"success": False, "error": str(e)}
                
                if result["original_image"].get("size_bytes") and result["optimized_image"].get("size_bytes"):
                    orig_size = result["original_image"]["size_bytes"]
                    opt_size = result["optimized_image"]["size_bytes"]
                    size_diff = orig_size - opt_size
                    size_diff_pct = (size_diff / orig_size * 100) if orig_size > 0 else 0
                    
                    result["comparison"]["size_reduction_bytes"] = size_diff
                    result["comparison"]["size_reduction_percent"] = round(size_diff_pct, 2)
                
                if result["comparison"].get("dive_analysis", {}).get("efficiency_improvement") is not None:
                    result["comparison"]["efficiency_improvement"] = result["comparison"]["dive_analysis"]["efficiency_improvement"]
                
                if result["comparison"].get("dive_analysis", {}).get("wasted_space_reduction") is not None:
                    result["comparison"]["wasted_space_reduction_bytes"] = result["comparison"]["dive_analysis"]["wasted_space_reduction"]
                
                result["comparison"]["estimated"] = False
                result["estimated"] = False
            
            if result["build_status"] == "success":
                result["success"] = True
            else:
                result["success"] = bool(llm_results.get("success"))
            
        finally:
            if cleanup_repo and os.path.exists(repo_path):
                if progress_callback:
                    progress_callback(f"Cleaning up {repo_name}...")
                delete_repo(repo_path)
            
            if cleanup_images:
                if image_exists(original_tag):
                    remove_image(original_tag)
                if image_exists(optimized_tag):
                    remove_image(optimized_tag)
    
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
    
    return result


def process_all_repos(
    repos_file: str,
    api_key: str,
    model: str,
    build_timeout: int = 300,
    skip_test: bool = False,
    cleanup_repo: bool = True,
    cleanup_images: bool = False,
    max_repos: Optional[int] = None,
    max_workers: int = 3,
    rpm_limit: int = 15,
    tpm_limit: int = 250000,
    rpd_limit: int = 1000,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> List[Dict[str, Any]]:
    """Process all repositories from a file with parallel processing.
    
    Args:
        repos_file: Path to file containing repository URLs
        api_key: Gemini API key
        model: Gemini model to use
        build_timeout: Build timeout in seconds
        skip_test: Whether to skip Docker build/test stage
        cleanup_repo: Whether to cleanup cloned repos after processing
        cleanup_images: Whether to cleanup Docker images after processing
        max_repos: Maximum number of repos to process (None = all)
        max_workers: Number of parallel workers (default: 3, set to 1 for sequential)
        rpm_limit: Requests per minute limit (default: 15)
        tpm_limit: Tokens per minute limit (default: 250000)
        rpd_limit: Requests per day limit (default: 1000)
        progress_callback: Optional callback function(progress_msg, current, total)
        
    Returns:
        List of analysis results, one per repository
    """
    reset_rate_limiter()
    rate_limiter = get_rate_limiter(
        rpm=rpm_limit,
        tpm=tpm_limit,
        rpd=rpd_limit,
        tokens_per_request=10000
    )
    
    repos = get_all_repos_from_file(repos_file)
    
    if not repos:
        return []
    
    if max_repos:
        repos = repos[:max_repos]
    
    if max_workers > rpm_limit:
        print(f"[WARNING] max_workers ({max_workers}) exceeds RPM limit ({rpm_limit}). "
              f"Consider reducing max_workers to avoid rate limit errors.")
    
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    repos_dir = os.path.join(current_file_dir, "cloned_repos")
    os.makedirs(repos_dir, exist_ok=True)
    
    total = len(repos)
    results = []
    
    completed_lock = Lock()
    completed_count = [0]
    active_workers = [0]
    
    def process_with_pipeline(repo_url: str, index: int) -> Dict[str, Any]:
        """Process a single repo with its own pipeline instance (thread-safe).
        
        Args:
            repo_url: Repository URL to process
            index: Index of the repo (1-based)
            
        Returns:
            Analysis result dictionary
        """
        pipeline = DockerfilePipeline(
            api_key=api_key,
            model=model,
            build_timeout=build_timeout
        )
        
        with completed_lock:
            active_workers[0] += 1
            if progress_callback:
                progress_callback(f"Starting {index}/{total}: {repo_url} (Active workers: {active_workers[0]})", index, total)
        
        try:
            result = process_single_repo(
                repo_url=repo_url,
                pipeline=pipeline,
                repos_dir=repos_dir,
                skip_test=skip_test,
                cleanup_repo=cleanup_repo,
                cleanup_images=cleanup_images,
                progress_callback=lambda msg: (
                    progress_callback(f"[{index}/{total}] {msg}", index, total) 
                    if progress_callback else None
                )
            )
            
            if progress_callback:
                with completed_lock:
                    active_workers[0] -= 1
                    completed_count[0] += 1
                    progress_callback(
                        f"Completed {completed_count[0]}/{total} ({repo_url}) [Active: {active_workers[0]}]", 
                        completed_count[0], 
                        total
                    )
            
            return result
        except Exception as e:
            error_result = {
                "repo_url": repo_url,
                "repo_name": sanitize_repo_name(repo_url),
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "original_image": {},
                "optimized_image": {},
                "dynamic_analysis": {},
                "comparison": {}
            }
            if progress_callback:
                with completed_lock:
                    active_workers[0] -= 1
                    completed_count[0] += 1
            return error_result
    
    if max_workers == 1:
        for i, repo_url in enumerate(repos, 1):
            result = process_with_pipeline(repo_url, i)
            results.append(result)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(process_with_pipeline, repo_url, i+1): (repo_url, i+1)
                for i, repo_url in enumerate(repos)
            }
            
            results_dict = {}
            for future in as_completed(future_to_repo):
                repo_url, index = future_to_repo[future]
                try:
                    result = future.result()
                    results_dict[index] = result
                except Exception as e:
                    error_result = {
                        "repo_url": repo_url,
                        "repo_name": sanitize_repo_name(repo_url),
                        "success": False,
                        "error": f"Execution error: {str(e)}",
                        "build_status": "error",
                        "original_image": {},
                        "optimized_image": {},
                        "dynamic_analysis": {},
                        "comparison": {}
                    }
                    results_dict[index] = error_result
            
            results = [results_dict[i] for i in sorted(results_dict.keys())]
    
    try:
        rate_status = rate_limiter.get_status()
        if results:
            results[0]["rate_limit_status"] = rate_status
    except:
        pass
    
    build_summary = {
        "total_repos": len(results),
        "successful_builds": sum(1 for r in results if r.get("build_status") == "success"),
        "failed_builds": sum(1 for r in results if r.get("build_status") and r.get("build_status") != "success"),
        "estimated_results": sum(1 for r in results if r.get("estimated", False)),
        "actual_results": sum(1 for r in results if not r.get("estimated", False) and r.get("build_status") == "success")
    }
    
    for result in results:
        result["batch_summary"] = build_summary
    
    return results

