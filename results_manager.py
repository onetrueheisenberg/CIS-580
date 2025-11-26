"""Results storage and retrieval for batch Docker analysis.

This module provides functions to save and load analysis results
from batch processing of multiple repositories.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


def save_results(results: List[Dict[str, Any]], output_file: str) -> None:
    """Save batch analysis results to a JSON file.
    
    Args:
        results: List of analysis results, one per repository
        output_file: Path to output JSON file
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)


def load_results(input_file: str) -> List[Dict[str, Any]]:
    """Load batch analysis results from a JSON file.
    
    Args:
        input_file: Path to input JSON file
        
    Returns:
        List of analysis results, one per repository
    """
    if not os.path.exists(input_file):
        return []
    
    with open(input_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_results_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate summary statistics from batch results.
    
    Args:
        results: List of analysis results
        
    Returns:
        Dictionary with summary statistics:
        - total_repos: Total number of repositories processed
        - successful_repos: Number of successfully processed repos
        - failed_repos: Number of failed repos
        - avg_size_reduction_percent: Average size reduction percentage
        - total_size_saved_bytes: Total size saved across all repos
        - avg_efficiency_improvement: Average efficiency improvement
        - repos_with_improvements: Number of repos with improvements
    """
    if not results:
        return {
            "total_repos": 0,
            "successful_repos": 0,
            "failed_repos": 0,
            "avg_size_reduction_percent": 0,
            "total_size_saved_bytes": 0,
            "avg_efficiency_improvement": 0,
            "repos_with_improvements": 0
        }
    
    successful = [r for r in results if r.get("success", False)]
    failed = [r for r in results if not r.get("success", False)]
    
    size_reductions = []
    efficiency_improvements = []
    total_size_saved = 0
    repos_with_improvements = 0
    
    for result in successful:
        comparison = result.get("comparison", {})
        
        size_reduction_pct = comparison.get("size_reduction_percent")
        if size_reduction_pct is not None:
            size_reductions.append(size_reduction_pct)
            size_reduction_bytes = comparison.get("size_reduction_bytes", 0)
            if size_reduction_bytes and size_reduction_bytes > 0:
                total_size_saved += size_reduction_bytes
                repos_with_improvements += 1
        
        efficiency_imp = comparison.get("efficiency_improvement")
        if efficiency_imp is not None:
            efficiency_improvements.append(efficiency_imp)
    
    avg_size_reduction = (
        sum(size_reductions) / len(size_reductions) if size_reductions else 0
    )
    avg_efficiency_imp = (
        sum(efficiency_improvements) / len(efficiency_improvements) 
        if efficiency_improvements else 0
    )
    
    return {
        "total_repos": len(results),
        "successful_repos": len(successful),
        "failed_repos": len(failed),
        "avg_size_reduction_percent": round(avg_size_reduction, 2),
        "total_size_saved_bytes": total_size_saved,
        "avg_efficiency_improvement": round(avg_efficiency_imp, 2),
        "repos_with_improvements": repos_with_improvements
    }


def export_to_csv(results: List[Dict[str, Any]], output_file: str) -> None:
    """Export results to CSV format.
    
    Args:
        results: List of analysis results
        output_file: Path to output CSV file
    """
    import csv
    
    if not results:
        return
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Define CSV columns
    fieldnames = [
        "repo_url",
        "repo_name",
        "success",
        "original_size_bytes",
        "optimized_size_bytes",
        "size_reduction_bytes",
        "size_reduction_percent",
        "efficiency_improvement",
        "wasted_space_reduction_bytes",
        "original_layer_count",
        "optimized_layer_count",
        "overall_score_original",
        "overall_score_optimized",
        "overall_score_improvement",
        "security_score_original",
        "security_score_optimized",
        "security_score_improvement",
        "efficiency_score_original",
        "efficiency_score_optimized",
        "efficiency_score_improvement",
        "best_practices_score_original",
        "best_practices_score_optimized",
        "best_practices_score_improvement",
        "error"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            row = {
                "repo_url": result.get("repo_url", ""),
                "repo_name": result.get("repo_name", ""),
                "success": result.get("success", False),
                "error": result.get("error", "")
            }
            
            # Image sizes
            orig_img = result.get("original_image", {})
            opt_img = result.get("optimized_image", {})
            row["original_size_bytes"] = orig_img.get("size_bytes")
            row["optimized_size_bytes"] = opt_img.get("size_bytes")
            
            # Comparison metrics
            comparison = result.get("comparison", {})
            row["size_reduction_bytes"] = comparison.get("size_reduction_bytes")
            row["size_reduction_percent"] = comparison.get("size_reduction_percent")
            row["efficiency_improvement"] = comparison.get("efficiency_improvement")
            row["wasted_space_reduction_bytes"] = comparison.get("wasted_space_reduction_bytes")
            
            # Layer counts
            orig_dive = orig_img.get("dive_analysis", {})
            opt_dive = opt_img.get("dive_analysis", {})
            row["original_layer_count"] = orig_dive.get("layer_count")
            row["optimized_layer_count"] = opt_dive.get("layer_count")
            
            # Dynamic analysis scores
            dyn_analysis = result.get("dynamic_analysis", {})
            llm_results = dyn_analysis.get("llm_pipeline_results", {})
            stages = llm_results.get("stages", {})
            
            # Original scores
            orig_analysis = stages.get("analysis", {}).get("result", {})
            orig_scores = orig_analysis.get("scores", {})
            row["overall_score_original"] = orig_scores.get("overall_score")
            row["security_score_original"] = orig_scores.get("security_score")
            row["efficiency_score_original"] = orig_scores.get("efficiency_score")
            row["best_practices_score_original"] = orig_scores.get("best_practices_score")
            
            # Validation scores (optimized)
            validation = stages.get("validation", {}).get("result", {})
            fixed_scores = validation.get("fixed_scores", {})
            row["overall_score_optimized"] = fixed_scores.get("overall_score")
            row["security_score_optimized"] = fixed_scores.get("security_score")
            row["efficiency_score_optimized"] = fixed_scores.get("efficiency_score")
            row["best_practices_score_optimized"] = fixed_scores.get("best_practices_score")
            
            # Score improvements
            improvements = validation.get("improvements", {})
            overall_imp = improvements.get("overall_score", {})
            security_imp = improvements.get("security_score", {})
            efficiency_imp = improvements.get("efficiency_score", {})
            best_practices_imp = improvements.get("best_practices_score", {})
            
            row["overall_score_improvement"] = overall_imp.get("improvement")
            row["security_score_improvement"] = security_imp.get("improvement")
            row["efficiency_score_improvement"] = efficiency_imp.get("improvement")
            row["best_practices_score_improvement"] = best_practices_imp.get("improvement")
            
            writer.writerow(row)

