#!/usr/bin/env python3
"""
Size Optimization Pipeline for Docker Images

This script processes all repositories through a two-stage optimization:
1. Static analysis to identify size-related improvements
2. LLM-based optimization building on static analysis results

Outputs:
- Original Dockerfiles
- Post-static-optimization Dockerfiles
- Post-LLM-optimization Dockerfiles
- Size savings estimates at each stage
"""

import argparse
import csv
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from dockerfile_optimizer import analyse_instructions, parse_dockerfile, find_dockerfiles
from llm_agents.dockerfile_llm_analyzer import DockerfileAnalyzer
from llm_agents.dockerfile_fixer import DockerfileFixer
from llm_agents.dockerfile_tester import DockerfileTester


SIZE_KEYWORDS = (
    "size", "layer", "cache", "no-cache", "multi-stage",
    "apt-get clean", "rm -rf /var/lib/apt/lists",
    "--no-install-recommends", "--no-cache-dir", "COPY", "ADD",
    "reduce", "smaller", "minimize", "compress"
)


@dataclass
class SizeOptimizationResult:
    repo_url: str
    dockerfile_path: str
    original_dockerfile: str
    static_optimized_dockerfile: Optional[str] = None
    llm_optimized_dockerfile: Optional[str] = None
    static_size_issues_found: int = 0
    static_estimated_savings_kb: float = 0.0
    llm_size_issues_found: int = 0
    llm_estimated_savings_kb: float = 0.0
    total_estimated_savings_kb: float = 0.0
    original_image_size: Optional[str] = None
    static_image_size: Optional[str] = None
    llm_image_size: Optional[str] = None
    original_build_success: bool = False
    static_build_success: bool = False
    llm_build_success: bool = False
    error: Optional[str] = None


def filter_size_recommendations(recommendations: List[dict]) -> List[dict]:
    """Filter recommendations to only include size-related ones."""
    filtered = []
    for rec in recommendations:
        message = rec.get("message", "").lower()
        if any(keyword in message for keyword in SIZE_KEYWORDS):
            filtered.append(rec)
    return filtered


def apply_static_size_optimizations(dockerfile_content: str) -> tuple[str, List[dict]]:
    """Apply static size optimizations to a Dockerfile."""
    instructions = parse_dockerfile(dockerfile_content)
    all_recs = analyse_instructions(instructions)
    size_recs = filter_size_recommendations(all_recs)
    
    optimized = dockerfile_content
    changes_made = []
    
    for rec in size_recs:
        message = rec.get("message", "")
        
        if "--no-install-recommends" in message and "apt-get install" in optimized:
            lines = optimized.split('\n')
            new_lines = []
            for line in lines:
                if "apt-get install" in line and "--no-install-recommends" not in line:
                    line = line.replace("apt-get install", "apt-get install --no-install-recommends")
                    changes_made.append("Added --no-install-recommends to apt-get install")
                new_lines.append(line)
            optimized = '\n'.join(new_lines)
        
        if "apt-get clean" in message:
            lines = optimized.split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                new_lines.append(line)
                if "apt-get install" in line and "&&" in line:
                    if not any("rm -rf /var/lib/apt/lists" in l for l in lines[max(0,i-2):min(len(lines),i+3)]):
                        stripped = line.rstrip()
                        if stripped.endswith("\\"):
                            new_lines[-1] = stripped + "\n    && rm -rf /var/lib/apt/lists/* \\"
                        elif not stripped.endswith("&&"):
                            new_lines[-1] = stripped + " && rm -rf /var/lib/apt/lists/*"
                        changes_made.append("Added apt cache cleanup")
            optimized = '\n'.join(new_lines)
        
        if "--no-cache-dir" in message and "pip install" in optimized:
            lines = optimized.split('\n')
            new_lines = []
            for line in lines:
                if "pip install" in line and "--no-cache-dir" not in line:
                    line = line.replace("pip install", "pip install --no-cache-dir")
                    changes_made.append("Added --no-cache-dir to pip install")
                new_lines.append(line)
            optimized = '\n'.join(new_lines)
    
    if optimized == dockerfile_content:
        return dockerfile_content, []
    
    return optimized, changes_made


def estimate_size_savings(recommendations: List[dict], llm_data: Optional[Dict] = None) -> float:
    """Estimate potential size savings in KB from recommendations."""
    savings = 0.0
    
    for rec in recommendations:
        message = rec.get("message", "").lower()
        if "--no-install-recommends" in message:
            savings += 50000
        elif "cache" in message or "clean" in message:
            savings += 10000
        elif "--no-cache-dir" in message:
            savings += 5000
        elif "multi-stage" in message:
            savings += 100000
        elif "layer" in message:
            savings += 20000
    
    if llm_data:
        estimated_waste = llm_data.get("estimated_wasted_space_kb", 0)
        if estimated_waste > 0:
            savings += estimated_waste
    
    return savings


def apply_llm_size_optimization(dockerfile_content: str, api_key: Optional[str] = None, model: Optional[str] = None) -> tuple[Optional[str], Dict]:
    """Apply LLM-based size optimization to a Dockerfile."""
    try:
        analyzer = DockerfileAnalyzer(api_key=api_key, model=model)
        
        print("  Analyzing with LLM (size-focused)...", end="", flush=True)
        
        size_focused_analysis = analyzer.dynamic_llm_analysis(dockerfile_content)
        
        if not size_focused_analysis.get("success"):
            print(" Failed")
            return None, {"error": size_focused_analysis.get("error", "LLM analysis failed")}
        
        print(" Done")
        
        llm_data = size_focused_analysis.get("data", {})
        
        perf_issues = llm_data.get("performance_issues", [])
        opt_opps = llm_data.get("optimization_opportunities", [])
        
        # size_issues = [issue for issue in (perf_issues + opt_opps) if any(kw in issue.lower() for kw in SIZE_KEYWORDS)]
              # Filter for size-related issues (strings)
        size_issues_strings = [issue for issue in (perf_issues + opt_opps) if any(kw in str(issue).lower() for kw in SIZE_KEYWORDS)]
        
        # Convert strings to dict format for estimate_size_savings
        size_issues = [{"message": issue} for issue in size_issues_strings]
        
        if not size_issues:
            print("  No size-related issues found by LLM")
            return dockerfile_content, {"no_changes": True, "llm_data": llm_data}
        
        fixer = DockerfileFixer(api_key=api_key, model=model)
        
        size_focused_analysis_for_fixer = {
            "llm_analysis": {
                "success": True,
                "data": {
                    "security_risks": [],
                    "performance_issues": size_issues[:10],
                    "optimization_opportunities": [],
                    "runtime_concerns": [],
                    "best_practices_missing": [],
                    "recommendations": []
                }
            },
            "scores": {
                "security_score": 100,
                "efficiency_score": 50,
                "best_practices_score": 100,
                "overall_score": 70
            }
        }
        
        print("  Applying LLM optimizations...", end="", flush=True)
        fix_result = fixer.fix_dockerfile(dockerfile_content, size_focused_analysis_for_fixer)
        print(" Done")
        
        if fix_result.get("success"):
            return fix_result.get("fixed_dockerfile"), {"llm_data": llm_data, "size_issues": size_issues}
        else:
            return None, {"error": fix_result.get("error", "Failed to apply LLM fixes")}
    
    except Exception as e:
        print(f" Error: {str(e)}")
        return None, {"error": str(e)}


def clone_repo(url: str, base_dir: str) -> str:
    """Clone a repository if it doesn't exist."""
    repo_name = url.rstrip("/").split("/")[-1]
    dest = os.path.join(base_dir, repo_name)
    if not os.path.exists(dest):
        print(f"  Cloning {repo_name}...")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", url, dest],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"  Failed to clone: {e}")
    return dest


def select_best_dockerfile(dockerfiles: List[str]) -> Optional[str]:
    """Select the most likely to succeed dockerfile from a list.
    Prefers 'Dockerfile' over others, then first one found."""
    if not dockerfiles:
        return None
    
    # Prefer exact "Dockerfile" match
    for df in dockerfiles:
        if os.path.basename(df).lower() == "dockerfile":
            return df
    
    # Otherwise return the first one
    return dockerfiles[0]


def get_image_size(image_name: str) -> Optional[str]:
    """Get the size of a Docker image using docker inspect."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format={{.Size}}", image_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            size_bytes = float(result.stdout.strip())
            # Convert to human-readable format
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    if unit == 'B':
                        return f"{int(size_bytes)}{unit}"
                    return f"{size_bytes:.2f}{unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f}TB"
    except Exception:
        pass
    return None


def process_repository(
    repo_url: str,
    repos_dir: str,
    output_dir: str,
    api_key: Optional[str],
    model: Optional[str],
    build_images: bool = False,
) -> Optional[SizeOptimizationResult]:
    """Process a single repository through the size optimization pipeline.
    Selects one dockerfile, builds original, static, and LLM versions, and compares sizes."""
    print(f"\n{'='*70}")
    print(f"Processing: {repo_url}")
    print(f"{'='*70}")
    
    repo_path = clone_repo(repo_url, repos_dir)
    
    if not os.path.exists(repo_path):
        return SizeOptimizationResult(
            repo_url=repo_url,
            dockerfile_path="",
            original_dockerfile="",
            error="Failed to clone repository"
        )
    
    dockerfiles = find_dockerfiles(repo_path)
    
    if not dockerfiles:
        print("No Dockerfiles found")
        return SizeOptimizationResult(
            repo_url=repo_url,
            dockerfile_path="",
            original_dockerfile="",
            error="No Dockerfiles found"
        )
    
    # Select one dockerfile (most likely to succeed)
    dockerfile_path = select_best_dockerfile(dockerfiles)
    if not dockerfile_path:
        return SizeOptimizationResult(
            repo_url=repo_url,
            dockerfile_path="",
            original_dockerfile="",
            error="Failed to select dockerfile"
        )
    
    print(f"\nSelected Dockerfile: {dockerfile_path}")
    
    try:
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        return SizeOptimizationResult(
            repo_url=repo_url,
            dockerfile_path=dockerfile_path,
            original_dockerfile="",
            error=f"Failed to read Dockerfile: {e}"
        )
    
    result = SizeOptimizationResult(
        repo_url=repo_url,
        dockerfile_path=dockerfile_path,
        original_dockerfile=original_content
    )
    
    repo_name = repo_url.rstrip("/").split("/")[-1]
    dockerfile_name = Path(dockerfile_path).name
    base_name = f"{repo_name}_{dockerfile_name}"
    
    # Save original
    original_save_path = os.path.join(output_dir, f"{base_name}_original")
    with open(original_save_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    print(f"  Saved original → {original_save_path}")
    
    # Step 1: Apply static optimizations
    print("\n  Step 1: Static Size Optimization")
    static_optimized, changes = apply_static_size_optimizations(original_content)
    
    if static_optimized != original_content:
        result.static_optimized_dockerfile = static_optimized
        result.static_size_issues_found = len(changes)
        
        instructions = parse_dockerfile(original_content)
        all_recs = analyse_instructions(instructions)
        size_recs = filter_size_recommendations(all_recs)
        result.static_estimated_savings_kb = estimate_size_savings(size_recs)
        
        static_save_path = os.path.join(output_dir, f"{base_name}_static_optimized")
        with open(static_save_path, 'w', encoding='utf-8') as f:
            f.write(static_optimized)
        print(f"  Applied {len(changes)} static optimizations")
        print(f"  Saved static optimized → {static_save_path}")
        
        base_for_llm = static_optimized
    else:
        print("  No static optimizations applied")
        base_for_llm = original_content
        static_save_path = None
    
    # Step 2: Apply LLM optimizations
    print("\n  Step 2: LLM Size Optimization")
    llm_optimized, llm_result = apply_llm_size_optimization(base_for_llm, api_key, model)
    
    if llm_optimized and llm_optimized != base_for_llm:
        result.llm_optimized_dockerfile = llm_optimized
        
        llm_data = llm_result.get("llm_data", {})
        size_issues = llm_result.get("size_issues", [])
        result.llm_size_issues_found = len(size_issues)
        result.llm_estimated_savings_kb = estimate_size_savings(size_issues, llm_data)
        result.total_estimated_savings_kb = result.static_estimated_savings_kb + result.llm_estimated_savings_kb
        
        llm_save_path = os.path.join(output_dir, f"{base_name}_llm_optimized")
        with open(llm_save_path, 'w', encoding='utf-8') as f:
            f.write(llm_optimized)
        print(f"  Applied LLM optimizations")
        print(f"  Saved LLM optimized → {llm_save_path}")
    elif llm_result.get("no_changes"):
        print("  LLM found no additional size optimizations needed")
        result.total_estimated_savings_kb = result.static_estimated_savings_kb
        llm_save_path = None
    else:
        error_msg = llm_result.get("error", "Unknown error")
        print(f"  LLM optimization failed: {error_msg}")
        result.error = error_msg if not result.error else f"{result.error}; LLM: {error_msg}"
        llm_save_path = None

    # Build all three versions and compare sizes
    if build_images:
        tester = DockerfileTester()
        if not tester.docker_available:
            print("  Docker CLI not available – skipping image builds")
        else:
            image_base = repo_name.replace("/", "_").replace("-", "_").lower()
            
            # Build original
            original_tag = f"{image_base}_original"
            print(f"\n  Building original image: {original_tag}")
            try:
                build_res = tester._build_image(original_save_path, repo_path, original_tag)
                result.original_build_success = build_res.get("success", False)
                if result.original_build_success:
                    result.original_image_size = build_res.get("final_size") or get_image_size(original_tag)
                    print(f"    Build successful. Size: {result.original_image_size or 'N/A'}")
                else:
                    print(f"    Build failed: {build_res.get('errors', 'Unknown error')[:200]}")
            except Exception as e:
                print(f"    Build error: {str(e)[:200]}")
            
            # Build static optimized
            if static_save_path and os.path.exists(static_save_path):
                static_tag = f"{image_base}_static"
                print(f"\n  Building static optimized image: {static_tag}")
                try:
                    build_res = tester._build_image(static_save_path, repo_path, static_tag)
                    result.static_build_success = build_res.get("success", False)
                    if result.static_build_success:
                        result.static_image_size = build_res.get("final_size") or get_image_size(static_tag)
                        print(f"    Build successful. Size: {result.static_image_size or 'N/A'}")
                    else:
                        print(f"    Build failed: {build_res.get('errors', 'Unknown error')[:200]}")
                except Exception as e:
                    print(f"    Build error: {str(e)[:200]}")
            
            # Build LLM optimized
            if llm_save_path and os.path.exists(llm_save_path):
                llm_tag = f"{image_base}_llm"
                print(f"\n  Building LLM optimized image: {llm_tag}")
                try:
                    build_res = tester._build_image(llm_save_path, repo_path, llm_tag)
                    result.llm_build_success = build_res.get("success", False)
                    if result.llm_build_success:
                        result.llm_image_size = build_res.get("final_size") or get_image_size(llm_tag)
                        print(f"    Build successful. Size: {result.llm_image_size or 'N/A'}")
                    else:
                        print(f"    Build failed: {build_res.get('errors', 'Unknown error')[:200]}")
                except Exception as e:
                    print(f"    Build error: {str(e)[:200]}")
            
            # Print comparison
            print("\n  Image size comparison:")
            print(f"    Original: {result.original_image_size or 'BUILD_FAILED'}")
            print(f"    Static:   {result.static_image_size or 'BUILD_FAILED'}")
            print(f"    LLM:      {result.llm_image_size or 'BUILD_FAILED'}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Size optimization pipeline for Docker images")
    parser.add_argument("--repos-file", default="docker_repos.txt", help="File with repository URLs")
    parser.add_argument("--output-dir", default="optimized_dockerfiles", help="Directory for optimized Dockerfiles")
    parser.add_argument("--repos-dir", default="cloned_repos", help="Directory for cloned repositories")
    parser.add_argument("--results-file", default="size_optimization_results.csv", help="CSV file for results")
    parser.add_argument("--api-key", help="Gemini API key")
    parser.add_argument("--model", help="Gemini model name")
    parser.add_argument("--limit", type=int, help="Limit number of repos to process")
    parser.add_argument(
        "--index",
        type=int,
        help="1-based index of repository in repos-file to process (build a single repo/image)",
    )
    parser.add_argument(
        "--build-images",
        action="store_true",
        default=True,
        help="Build Docker images for original and optimized Dockerfiles and compare sizes (default: True)",
    )
    parser.add_argument(
        "--no-build",
        dest="build_images",
        action="store_false",
        help="Skip building Docker images",
    )
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.repos_dir, exist_ok=True)
    
    api_key = args.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: No Gemini API key found. Set GEMINI_API_KEY or use --api-key")
        return 1
    
    with open(args.repos_file, 'r', encoding='utf-8') as f:
        repo_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    if args.index is not None:
        if args.index < 1 or args.index > len(repo_urls):
            print(f"ERROR: --index must be between 1 and {len(repo_urls)}, got {args.index}")
            return 1
        # Select a single repository by its 1-based index
        repo_urls = [repo_urls[args.index - 1]]
    
    if args.limit:
        repo_urls = repo_urls[:args.limit]
    
    print(f"\nProcessing {len(repo_urls)} repositories")
    print(f"Output directory: {args.output_dir}")
    print(f"Results file: {args.results_file}\n")
    
    all_results = []
    
    for i, repo_url in enumerate(repo_urls, 1):
        print(f"\n[{i}/{len(repo_urls)}] {repo_url}")
        try:
            result = process_repository(
                repo_url,
                args.repos_dir,
                args.output_dir,
                api_key,
                args.model,
                build_images=args.build_images,
            )
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"ERROR processing {repo_url}: {e}")
            all_results.append(SizeOptimizationResult(
                repo_url=repo_url,
                dockerfile_path="",
                original_dockerfile="",
                error=str(e)
            ))
    
    # Write results to CSV with simplified format
    with open(args.results_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Repository', 'Original Size', 'Static Size', 'LLM Size', 'Error']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in all_results:
            # Determine original size
            original_size = result.original_image_size
            if not original_size:
                if args.build_images and not result.original_build_success:
                    original_size = 'BUILD_FAILED'
                else:
                    original_size = 'N/A'
            
            # Determine static size
            if result.static_optimized_dockerfile:
                static_size = result.static_image_size
                if not static_size:
                    if args.build_images and not result.static_build_success:
                        static_size = 'BUILD_FAILED'
                    else:
                        static_size = 'N/A'
            else:
                static_size = 'NO_OPTIMIZATIONS'
            
            # Determine LLM size
            if result.llm_optimized_dockerfile:
                llm_size = result.llm_image_size
                if not llm_size:
                    if args.build_images and not result.llm_build_success:
                        llm_size = 'BUILD_FAILED'
                    else:
                        llm_size = 'N/A'
            else:
                llm_size = 'NO_OPTIMIZATIONS'
            
            row = {
                'Repository': result.repo_url,
                'Original Size': original_size,
                'Static Size': static_size,
                'LLM Size': llm_size,
                'Error': result.error or ''
            }
            writer.writerow(row)
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total repositories processed: {len(set(r.repo_url for r in all_results))}")
    print(f"Total Dockerfiles processed: {len([r for r in all_results if not r.error])}")
    print(f"Total static optimizations: {sum(r.static_size_issues_found for r in all_results)}")
    print(f"Total LLM optimizations: {sum(r.llm_size_issues_found for r in all_results)}")
    total_savings = sum(r.total_estimated_savings_kb for r in all_results)
    print(f"Total estimated savings: {total_savings/1024:.1f} MB ({total_savings:.0f} KB)")
    print(f"\nResults saved to: {args.results_file}")
    print(f"Optimized Dockerfiles saved to: {args.output_dir}/")
    
    return 0


if __name__ == "__main__":
    exit(main())
