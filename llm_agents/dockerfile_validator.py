from typing import Dict, List, Optional, Any

try:
    from .dockerfile_llm_analyzer import DockerfileAnalyzer
except ImportError:
    from dockerfile_llm_analyzer import DockerfileAnalyzer

class DockerfileValidator:
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.analyzer = DockerfileAnalyzer(
            api_key=api_key,
            model=model
        )
    
    def validate_fixes(
        self,
        original_analysis: Dict[str, Any],
        fixed_dockerfile: str
    ) -> Dict[str, Any]:
        import tempfile
        import os
        
        if not original_analysis:
            return {
                "success": False,
                "error": "Invalid original analysis provided",
                "original_scores": {},
                "fixed_scores": {},
                "improvements": {},
                "issues_comparison": {}
            }
        
        if not fixed_dockerfile or not fixed_dockerfile.strip():
            return {
                "success": False,
                "error": "Empty fixed Dockerfile provided",
                "original_scores": original_analysis.get("scores", {}),
                "fixed_scores": {},
                "improvements": {},
                "issues_comparison": {}
            }
        
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.Dockerfile', delete=False) as f:
                f.write(fixed_dockerfile)
                temp_path = f.name
            
            print(f"  Validating fixes...", end="", flush=True)
            try:
                fixed_analysis = self.analyzer.analyze_dockerfile(temp_path)
                print(" Done")
                
                fixed_llm = fixed_analysis.get("llm_analysis", {})
                if fixed_llm.get("success"):
                    fixed_data = fixed_llm.get("data", {})
                    fixed_scores = fixed_analysis.get("scores", {})
                    print(f"\n  [Validation Analysis] Success: True")
                    print(f"  [Validation Scores] Overall: {fixed_scores.get('overall_score', 0)}%, "
                          f"Security: {fixed_scores.get('security_score', 0)}%, "
                          f"Efficiency: {fixed_scores.get('efficiency_score', 0)}%")
                else:
                    print(f"\n  [Validation Analysis] Success: False - {fixed_llm.get('error', 'Unknown error')[:100]}")
            except Exception as e:
                print(" Failed")
                return {
                    "success": False,
                    "error": f"Failed to re-analyze fixed Dockerfile: {str(e)}",
                    "original_scores": original_analysis.get("scores", {}),
                    "fixed_scores": {},
                    "improvements": {},
                    "issues_comparison": {}
                }
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
        
        if "error" in fixed_analysis:
            error_msg = fixed_analysis.get("error", "Analysis failed")
            print(f"\n[WARNING] Validation analysis failed: {error_msg[:100]}")
            return {
                "success": False,
                "error": error_msg,
                "original_scores": original_analysis.get("scores", {}),
                "fixed_scores": original_analysis.get("scores", {}),
                "improvements": {},
                "issues_comparison": {},
                "validation_failed": True
            }
        
        llm_analysis = fixed_analysis.get("llm_analysis", {})
        if not llm_analysis.get("success", False):
            error_msg = llm_analysis.get("error", "LLM analysis failed")
            print(f"\n[WARNING] Validation LLM analysis failed: {error_msg[:100]}")
            return {
                "success": False,
                "error": error_msg,
                "original_scores": original_analysis.get("scores", {}),
                "fixed_scores": original_analysis.get("scores", {}),
                "improvements": {},
                "issues_comparison": {},
                "validation_failed": True
            }
        
        original_scores = original_analysis.get("scores", {})
        fixed_scores = fixed_analysis.get("scores", {})
        
        fixed_llm_analysis = fixed_analysis.get("llm_analysis", {})
        if not fixed_llm_analysis.get("success", False):
            print(f"\n[WARNING] Validation LLM analysis failed - using original scores")
            return {
                "success": False,
                "error": "Validation LLM analysis failed",
                "original_scores": original_scores,
                "fixed_scores": original_scores,
                "improvements": {},
                "issues_comparison": {},
                "validation_failed": True
            }
        
        score_values = [v for v in fixed_scores.values() if isinstance(v, (int, float))]
        if not fixed_scores or not score_values:
            print(f"\n[WARNING] Validation returned no scores - analysis may have failed")
            return {
                "success": False,
                "error": "Validation returned no scores",
                "original_scores": original_scores,
                "fixed_scores": original_scores,
                "improvements": {},
                "issues_comparison": {},
                "validation_failed": True
            }
        
        try:
            improvements = self._calculate_improvements(original_scores, fixed_scores)
            print(f"\n  [Improvements Calculated] {len(improvements)} score comparisons")
            for key in ["overall_score", "security_score", "efficiency_score", "best_practices_score"]:
                if key in improvements:
                    imp = improvements[key]
                    diff = imp["improvement"]
                    if diff > 0:
                        print(f"    {key}: +{diff:.1f} ({imp['percent_change']:.1f}% improvement)")
                    elif diff < 0:
                        print(f"    {key}: {diff:.1f} ({imp['percent_change']:.1f}% decrease)")
        except Exception as e:
            improvements = {}
            print(f"\n  [Warning] Failed to calculate improvements: {str(e)[:100]}")
        
        try:
            original_llm = original_analysis.get("llm_analysis", {}).get("data", {})
            fixed_llm = fixed_analysis.get("llm_analysis", {}).get("data", {})
            issues_comparison = self._compare_issues(original_llm, fixed_llm)
            
            print(f"\n  [Issues Comparison]")
            sec_comp = issues_comparison.get("security_risks", {})
            perf_comp = issues_comparison.get("performance_issues", {})
            missing_comp = issues_comparison.get("missing_practices", {})
            
            # Calculate how many issues were fixed (original - fixed)
            sec_original = sec_comp.get('original_count', 0)
            sec_fixed_count = sec_comp.get('fixed_count', 0)
            sec_fixed = max(0, sec_original - sec_fixed_count)
            sec_all_fixed = sec_original > 0 and sec_fixed_count == 0
            
            perf_original = perf_comp.get('original_count', 0)
            perf_fixed_count = perf_comp.get('fixed_count', 0)
            perf_fixed = max(0, perf_original - perf_fixed_count)
            perf_all_fixed = perf_original > 0 and perf_fixed_count == 0
            
            missing_original = missing_comp.get('original_count', 0)
            missing_fixed_count = missing_comp.get('fixed_count', 0)
            missing_fixed = max(0, missing_original - missing_fixed_count)
            missing_all_fixed = missing_original > 0 and missing_fixed_count == 0
            
            # Format output: show fixed count and if all were fixed
            sec_msg = f"Security Risks: {sec_original} → {sec_fixed_count}"
            if sec_all_fixed:
                sec_msg += f" (all {sec_original} fixed)"
            elif sec_fixed > 0:
                sec_msg += f" (fixed: {sec_fixed})"
            print(f"  {sec_msg}")
            
            perf_msg = f"Performance Issues: {perf_original} → {perf_fixed_count}"
            if perf_all_fixed:
                perf_msg += f" (all {perf_original} fixed)"
            elif perf_fixed > 0:
                perf_msg += f" (fixed: {perf_fixed})"
            print(f"  {perf_msg}")
            
            missing_msg = f"Missing Practices: {missing_original} → {missing_fixed_count}"
            if missing_all_fixed:
                missing_msg += f" (all {missing_original} fixed)"
            elif missing_fixed > 0:
                missing_msg += f" (fixed: {missing_fixed})"
            print(f"  {missing_msg}")
        except Exception as e:
            issues_comparison = {}
            print(f"\n  [Warning] Failed to compare issues: {str(e)[:100]}")
        
        return {
            "success": True,
            "original_scores": original_scores,
            "fixed_scores": fixed_scores,
            "improvements": improvements,
            "issues_comparison": issues_comparison,
            "fixed_analysis": fixed_analysis
        }
    
    def _calculate_improvements(
        self,
        original_scores: Dict[str, float],
        fixed_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        improvements = {}
        
        score_keys = [
            "overall_score", "security_score", "efficiency_score",
            "best_practices_score", "complexity_score", "maintainability_score"
        ]
        
        for key in score_keys:
            original = original_scores.get(key, 0)
            fixed = fixed_scores.get(key, 0)
            diff = fixed - original
            percent_change = ((fixed - original) / original * 100) if original > 0 else 0
            
            improvements[key] = {
                "original": round(original, 1),
                "fixed": round(fixed, 1),
                "improvement": round(diff, 1),
                "percent_change": round(percent_change, 1)
            }
        
        return improvements
    
    def _compare_issues(
        self,
        original_data: Dict[str, Any],
        fixed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        original_risks = set(original_data.get("security_risks", []))
        fixed_risks = set(fixed_data.get("security_risks", []))
        
        original_perf = set(original_data.get("performance_issues", []))
        fixed_perf = set(fixed_data.get("performance_issues", []))
        
        original_missing = set(original_data.get("best_practices_missing", []))
        fixed_missing = set(fixed_data.get("best_practices_missing", []))
        
        return {
            "security_risks": {
                "original_count": len(original_risks),
                "fixed_count": len(fixed_risks),
                "fixed": list(original_risks - fixed_risks),
                "new": list(fixed_risks - original_risks),
                "remaining": list(fixed_risks & original_risks)
            },
            "performance_issues": {
                "original_count": len(original_perf),
                "fixed_count": len(fixed_perf),
                "fixed": list(original_perf - fixed_perf),
                "new": list(fixed_perf - original_perf),
                "remaining": list(fixed_perf & original_perf)
            },
            "missing_practices": {
                "original_count": len(original_missing),
                "fixed_count": len(fixed_missing),
                "fixed": list(original_missing - fixed_missing),
                "new": list(fixed_missing - original_missing),
                "remaining": list(fixed_missing & original_missing)
            }
        }
    
    def print_comparison_report(self, validation_results: Dict[str, Any]) -> None:
        improvements = validation_results.get("improvements", {})
        issues = validation_results.get("issues_comparison", {})
        
        print("\n" + "="*60)
        print("VALIDATION REPORT - Before/After Comparison")
        print("="*60)
        
        print("\nSCORE IMPROVEMENTS:")
        for key, imp in improvements.items():
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
                print(f"  {key_name:25} {orig:6.1f} → {fixed:6.1f} (no change)")
        
        print("\nISSUES RESOLVED:")
        sec = issues.get("security_risks", {})
        print(f"Security Risks: {sec.get('original_count', 0)} → {sec.get('fixed_count', 0)} (fixed: {len(sec.get('fixed', []))}, new: {len(sec.get('new', []))})")
        
        perf = issues.get("performance_issues", {})
        print(f"Performance Issues: {perf.get('original_count', 0)} → {perf.get('fixed_count', 0)} (fixed: {len(perf.get('fixed', []))}, new: {len(perf.get('new', []))})")
        
        missing = issues.get("missing_practices", {})
        print(f"Missing Best Practices: {missing.get('original_count', 0)} → {missing.get('fixed_count', 0)} (fixed: {len(missing.get('fixed', []))}, new: {len(missing.get('new', []))})")
        
        print("\n" + "="*60 + "\n")



