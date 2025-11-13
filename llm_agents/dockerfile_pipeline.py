import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

if __package__ is None or __package__ == '':
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    from dockerfile_llm_analyzer import DockerfileAnalyzer, find_dockerfiles
    from dockerfile_fixer import DockerfileFixer
    from dockerfile_validator import DockerfileValidator
    from dockerfile_tester import DockerfileTester
else:
    from .dockerfile_llm_analyzer import DockerfileAnalyzer, find_dockerfiles
    from .dockerfile_fixer import DockerfileFixer
    from .dockerfile_validator import DockerfileValidator
    from .dockerfile_tester import DockerfileTester


class DockerfilePipeline:
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        build_timeout: int = 300
    ):
        self.analyzer = DockerfileAnalyzer(
            api_key=api_key,
            model=model
        )
        self.fixer = DockerfileFixer(
            api_key=api_key,
            model=model
        )
        self.validator = DockerfileValidator(
            api_key=api_key,
            model=model
        )
        self.tester = DockerfileTester(build_timeout=build_timeout)
    
    def optimize_dockerfile(
        self,
        dockerfile_path: str,
        skip_test: bool = False
    ) -> Dict[str, Any]:
        results = {
            "dockerfile_path": dockerfile_path,
            "stages": {}
        }
        
        # Stage 1: Analyze original
        print("\n" + "="*60)
        print("STAGE 1: ANALYZING ORIGINAL DOCKERFILE")
        print("="*60)
        try:
            original_analysis = self.analyzer.analyze_dockerfile(dockerfile_path)
            results["stages"]["analysis"] = {
                "success": True,
                "result": original_analysis
            }
            if "error" in original_analysis:
                print(f"\n[ERROR] Analysis failed: {original_analysis['error']}")
                results["stages"]["analysis"]["success"] = False
                return results
        except Exception as e:
            print(f"\n[ERROR] Analysis failed: {str(e)}")
            results["stages"]["analysis"] = {
                "success": False,
                "error": str(e)
            }
            return results
        
        try:
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                original_content = f.read()
        except Exception as e:
            print(f"\n[ERROR] Failed to read Dockerfile: {str(e)}")
            results["stages"]["analysis"]["success"] = False
            return results
        
        # Stage 2: Fix Dockerfile
        print("\n" + "="*60)
        print("STAGE 2: GENERATING OPTIMIZED DOCKERFILE")
        print("="*60)
        try:
            fix_result = self.fixer.fix_dockerfile(original_content, original_analysis)
            results["stages"]["fix"] = {
                "success": fix_result.get("success", False),
                "result": fix_result
            }
            if not fix_result.get("success"):
                print(f"\n[ERROR] Fix failed: {fix_result.get('error', 'Unknown error')}")
                return results
            fixed_content = fix_result["fixed_dockerfile"]
        except Exception as e:
            print(f"\n[ERROR] Fix failed: {str(e)}")
            results["stages"]["fix"] = {
                "success": False,
                "error": str(e)
            }
            return results
        
        # Stage 3: Validate fixes
        print("\n" + "="*60)
        print("STAGE 3: VALIDATING FIXES")
        print("="*60)
        try:
            validation_result = self.validator.validate_fixes(original_analysis, fixed_content)
            if validation_result.get("success"):
                results["stages"]["validation"] = {
                    "success": True,
                    "result": validation_result
                }
            else:
                print(f"\n[WARNING] Validation failed: {validation_result.get('error', 'Unknown error')}")
                results["stages"]["validation"] = {
                    "success": False,
                    "error": validation_result.get("error", "Validation failed"),
                    "result": validation_result
                }
        except Exception as e:
            print(f"\n[WARNING] Validation failed with exception: {str(e)}")
            results["stages"]["validation"] = {
                "success": False,
                "error": str(e)
            }
        
        # Stage 4: Test Dockerfile (optional)
        if not skip_test:
            print("\n" + "="*60)
            print("STAGE 4: TESTING DOCKERFILE")
            print("="*60)
            try:
                if not self.tester.docker_available:
                    print("\n[WARNING] Docker CLI not available, skipping test")
                    results["stages"]["test"] = {
                        "success": None,
                        "skipped": True,
                        "reason": "Docker CLI not available"
                    }
                else:
                    test_result = self.tester.test_dockerfile(
                        fixed_content,
                        dockerfile_path,
                        os.path.dirname(dockerfile_path) or "."
                    )
                    results["stages"]["test"] = {
                        "success": test_result.get("success", False),
                        "result": test_result
                    }
                    
                    if test_result.get("image_name"):
                        try:
                            self.tester.cleanup_image(test_result["image_name"])
                        except Exception:
                            pass
            except Exception as e:
                print(f"\n[WARNING] Test failed: {str(e)}")
                results["stages"]["test"] = {
                    "success": False,
                    "error": str(e)
                }
        else:
            results["stages"]["test"] = {
                "success": None,
                "skipped": True
            }
        
        results["original_dockerfile"] = original_content
        results["fixed_dockerfile"] = fixed_content
        results["original_analysis"] = original_analysis
        results["success"] = (
            results["stages"]["analysis"].get("success", False) and
            results["stages"]["fix"].get("success", False)
        )
        
        return results
    
    def print_pipeline_report(self, results: Dict[str, Any]) -> None:
        print("\n" + "="*60)
        print("PIPELINE REPORT - COMPLETE OPTIMIZATION RESULTS")
        print("="*60)
        
        if not results.get("success"):
            print("\n[ERROR] Pipeline failed")
            for stage, stage_result in results.get("stages", {}).items():
                if not stage_result.get("success"):
                    print(f"  {stage.upper()}: {stage_result.get('error', 'Failed')}")
            print("\n" + "="*60 + "\n")
            return
        
        if "analysis" in results.get("stages", {}):
            analysis = results["stages"]["analysis"].get("result", {})
            scores = analysis.get("scores", {})
            print(f"\nORIGINAL DOCKERFILE SCORES:")
            print(f"  Overall Score:        {scores.get('overall_score', 0):.1f}%")
            print(f"  Security Score:       {scores.get('security_score', 0):.1f}%")
            print(f"  Efficiency Score:     {scores.get('efficiency_score', 0):.1f}%")
            print(f"  Best Practices Score: {scores.get('best_practices_score', 0):.1f}%")
        
        # Validation stage
        if "validation" in results.get("stages", {}):
            validation = results["stages"]["validation"].get("result", {})
            validation_success = validation.get("success", False)
            validation_failed = validation.get("validation_failed", False)
            
            if validation_success and not validation_failed:
                improvements = validation.get("improvements", {})
                if improvements:
                    print(f"\nIMPROVEMENTS AFTER OPTIMIZATION:")
                    for key, imp in improvements.items():
                        if key in ["overall_score", "security_score", "efficiency_score", "best_practices_score"]:
                            key_name = key.replace("_", " ").title()
                            orig = imp["original"]
                            fixed = imp["fixed"]
                            diff = imp["improvement"]
                            pct = imp["percent_change"]
                            if diff > 0:
                                print(f"  {key_name:25} {orig:6.1f} → {fixed:6.1f} (+{diff:5.1f}, +{pct:5.1f}%)")
                            elif diff < 0:
                                print(f"  {key_name:25} {orig:6.1f} → {fixed:6.1f} ({diff:5.1f}, {pct:5.1f}%)")
                else:
                    print(f"\n[WARNING] No improvement data available")
            else:
                print(f"\n[WARNING] Validation could not complete - comparison unavailable")
                if validation.get("error"):
                    error_msg = validation.get('error', 'Unknown error')
                    print(f"  Reason: {error_msg[:150]}")
                if validation_failed:
                    print(f"  Note: Validation detected default/fallback scores - LLM analysis may have failed")
        
        if "test" in results.get("stages", {}):
            test = results["stages"]["test"]
            if test.get("skipped"):
                print(f"\nTEST: Skipped")
            else:
                test_result = test.get("result", {})
                print(f"\nTEST RESULTS:")
                print(f"  Build: {'SUCCESS' if test_result.get('build_success') else 'FAILED'}")
                if test_result.get("build_time"):
                    print(f"  Build Time: {test_result.get('build_time', 0):.2f} seconds")
                if test_result.get("step_count"):
                    print(f"  Build Steps: {test_result.get('step_count')}")
                if test_result.get("final_size"):
                    print(f"  Image Size: {test_result.get('final_size')}")
                if test_result.get("build_errors"):
                    print(f"  Build Errors: {test_result.get('build_errors')[:200]}")
                print(f"  Test: {'SUCCESS' if test_result.get('test_success') else 'FAILED'}")
                if test_result.get("test_output"):
                    print(f"  Test Output: {test_result.get('test_output')[:200]}")
        
        print("\n" + "="*60 + "\n")


def clone_repo(url: str, base_dir: str) -> str:
    repo_name = url.rstrip("/").split("/")[-1]
    dest = os.path.join(base_dir, repo_name)
    if not os.path.exists(dest):
        print(f"  Cloning repository: {url}...", end="", flush=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", url, dest],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(" Done")
    else:
        print(f"  Repository already exists: {dest}")
    return dest


def delete_repo(repo_path: str) -> None:
    if os.path.exists(repo_path):
        print(f"  Cleaning up: {repo_path}...", end="", flush=True)
        try:
            shutil.rmtree(repo_path)
            print(" Done")
        except Exception as e:
            print(f" Error: {e}")


def get_first_repo_from_file(repos_file: str) -> Optional[str]:
    try:
        with open(repos_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and line.startswith("http"):
                    return line
        return None
    except FileNotFoundError:
        print(f"ERROR: File not found: {repos_file}", file=sys.stderr)
        return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Multi-Agent Dockerfile Optimization Pipeline"
    )
    parser.add_argument(
        "dockerfile_path",
        nargs="?",
        help="Path to Dockerfile to optimize (ignored if --repos-file is used)"
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API key (or set GEMINI_API_KEY env var)",
        default=None
    )
    parser.add_argument(
        "--model",
        help="Gemini model to use (default: gemini-2.5-flash-lite)",
        default=None
    )
    parser.add_argument(
        "--skip-test",
        action="store_true",
        help="Skip Docker build/test stage"
    )
    parser.add_argument(
        "--output",
        help="Output path for fixed Dockerfile",
        default=None
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--build-timeout",
        type=int,
        help="Build timeout in seconds",
        default=300
    )
    parser.add_argument(
        "--repos-file",
        help="Process repo(s) from docker_repos.txt file (clones, analyzes Dockerfile(s), then deletes)",
        default=None
    )
    parser.add_argument(
        "--first-only",
        action="store_true",
        help="Only process the first Dockerfile found (default: process all Dockerfiles)",
        default=False
    )
    
    args = parser.parse_args()
    
    api_key = args.api_key
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("gemini_api_key")
    
    if args.model:
        model = args.model
    else:
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    
    try:
        pipeline = DockerfilePipeline(
            api_key=api_key,
            model=model,
            build_timeout=args.build_timeout
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    
    if args.repos_file:
        repos_file_path = args.repos_file
        if not os.path.exists(repos_file_path):
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            parent_path = os.path.join(parent_dir, repos_file_path)
            if os.path.exists(parent_path):
                repos_file_path = parent_path
        
        repo_url = get_first_repo_from_file(repos_file_path)
        if not repo_url:
            print("ERROR: No valid repository URL found in file.", file=sys.stderr)
            sys.exit(1)
        
        print(f"Processing first repository from {args.repos_file}:")
        print(f"  URL: {repo_url}")
        
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_file_dir)
        repos_dir = os.path.join(parent_dir, "cloned_repos")
        os.makedirs(repos_dir, exist_ok=True)
        
        repo_path = clone_repo(repo_url, repos_dir)
        
        try:
            dockerfiles = find_dockerfiles(repo_path)
            if not dockerfiles:
                print(f"No Dockerfiles found in {repo_path}")
                sys.exit(0)
            
            print(f"\nFound {len(dockerfiles)} Dockerfile(s):")
            for i, df in enumerate(dockerfiles, 1):
                print(f"  {i}. {df}")
            
            if args.first_only:
                dockerfiles = dockerfiles[:1]
                print(f"\nProcessing first Dockerfile only (--first-only flag set):")
            else:
                print(f"\nProcessing all {len(dockerfiles)} Dockerfile(s):")
            
            all_results = []
            for i, dockerfile_path in enumerate(dockerfiles, 1):
                if len(dockerfiles) > 1:
                    print(f"\n{'='*60}")
                    print(f"DOCKERFILE {i}/{len(dockerfiles)}: {dockerfile_path}")
                    print(f"{'='*60}")
                
                results = pipeline.optimize_dockerfile(dockerfile_path, skip_test=args.skip_test)
                
                if not args.json:
                    pipeline.print_pipeline_report(results)
                
                validation = results.get("stages", {}).get("validation", {}).get("result", {})
                if validation.get("success") and not validation.get("validation_failed"):
                    improvements = validation.get("improvements", {})
                    overall_improvement = improvements.get("overall_score", {}).get("improvement", 0)
                    
                    if overall_improvement < 0:
                        print(f"\n[WARNING] Optimization resulted in LOWER scores!")
                        print(f"  Overall score decreased by {abs(overall_improvement):.1f} points")
                        print(f"  The 'optimized' Dockerfile may not be better than the original.")
                        print(f"  Consider reviewing the changes before using the optimized version.")
                
                if results.get("success") and "fixed_dockerfile" in results:
                    output_path = args.output or dockerfile_path
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(results["fixed_dockerfile"])
                    print(f"\nOptimized Dockerfile saved to: {output_path}")
                
                all_results.append(results)
            
            if len(all_results) > 1:
                print(f"\n{'='*60}")
                print(f"SUMMARY: Processed {len(all_results)} Dockerfile(s)")
                print(f"{'='*60}")
                for i, result in enumerate(all_results, 1):
                    pipeline_success = result.get("success", False)
                    test_stage = result.get("stages", {}).get("test", {})
                    test_success = test_stage.get("success")
                    if test_stage.get("skipped"):
                        test_status = "SKIPPED"
                    elif test_success is False:
                        test_status = "TEST FAILED"
                    elif test_success is True:
                        test_status = "TEST PASSED"
                    else:
                        test_status = "UNKNOWN"
                    
                    path = result.get("dockerfile_path", f"Dockerfile {i}")
                    status = "SUCCESS" if pipeline_success and test_success is not False else "FAILED"
                    print(f"  {i}. {path}: {status} ({test_status})")
            
            if args.json:
                print(json.dumps(all_results if len(all_results) > 1 else all_results[0] if all_results else {}, indent=2, default=str))
            
            all_success = True
            for i, r in enumerate(all_results, 1):
                pipeline_success = r.get("success", False)
                test_stage = r.get("stages", {}).get("test", {})
                test_success = test_stage.get("success")
                if test_stage.get("skipped"):
                    test_success = True
                elif test_success is None:
                    test_success = True
                
                if not pipeline_success:
                    print(f"  [Result {i}] Pipeline failed")
                    all_success = False
                elif test_success is False:
                    print(f"  [Result {i}] Test failed")
                    all_success = False
            
            sys.exit(0 if all_success else 1)
        finally:
            delete_repo(repo_path)
    
    if not args.dockerfile_path:
        parser.print_help()
        print("\nERROR: Either provide dockerfile_path or use --repos-file", file=sys.stderr)
        sys.exit(1)
    
    results = pipeline.optimize_dockerfile(args.dockerfile_path, skip_test=args.skip_test)
    
    if not args.json:
        pipeline.print_pipeline_report(results)
    
    validation = results.get("stages", {}).get("validation", {}).get("result", {})
    if validation.get("success") and not validation.get("validation_failed"):
        improvements = validation.get("improvements", {})
        overall_improvement = improvements.get("overall_score", {}).get("improvement", 0)
        
        if overall_improvement < 0:
            print(f"\n[WARNING] Optimization resulted in LOWER scores!")
            print(f"  Overall score decreased by {abs(overall_improvement):.1f} points")
            print(f"  The 'optimized' Dockerfile may not be better than the original.")
            print(f"  Consider reviewing the changes before using the optimized version.")
    
    if results.get("success") and "fixed_dockerfile" in results:
        output_path = args.output or args.dockerfile_path
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(results["fixed_dockerfile"])
        print(f"\nOptimized Dockerfile saved to: {output_path}")
    
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    
    sys.exit(0 if results.get("success", False) else 1)


if __name__ == "__main__":
    main()

