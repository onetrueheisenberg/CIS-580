import json
import os
import sys
from typing import Dict, List, Optional, Any

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

try:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from rate_limiter import get_rate_limiter
except ImportError:
    get_rate_limiter = None

class DockerfileAnalyzer:    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_knowledge_base: bool = True
    ):
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY env var or pass api_key parameter."
            )
        
        self.api_key = api_key
        
        if not model:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        
        self.model = model
        
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "Google Generative AI library not installed. Install with: pip install google-generativeai"
            )
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)
        
        self.use_knowledge_base = use_knowledge_base
        self.knowledge_base = None
        if use_knowledge_base:
            try:
                from .knowledge_base import KnowledgeBase
                self.knowledge_base = KnowledgeBase()
                if not self.knowledge_base.base_images:
                    from .kb_initializer import initialize_knowledge_base
                    initialize_knowledge_base(self.knowledge_base)
            except Exception as e:
                print(f"  [WARNING] Knowledge base not available: {e}")
                self.use_knowledge_base = False
    
    def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if get_rate_limiter:
            try:
                rate_limiter = get_rate_limiter()
                estimated_tokens = len(prompt) // 4
                if system_prompt:
                    estimated_tokens += len(system_prompt) // 4
                wait_time = rate_limiter.wait_if_needed(estimated_tokens)
                if wait_time > 0:
                    print(f"  [Rate Limit] Waited {wait_time:.2f}s to respect API limits")
            except Exception as e:
                print(f"  [Warning] Rate limiter error: {e}")
        
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = self.client.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 4000,
                }
            )
            
            if not response:
                return "Error: No response from LLM"
            
            text = None
            if hasattr(response, 'text') and response.text:
                text = response.text
            elif hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text') and part.text]
                        if text_parts:
                            text = '\n'.join(text_parts)
            
            if not text:
                return "Error: No response from LLM"
            
            return text.strip()
        except Exception as e:
            error_msg = f"LLM API error: {str(e)}"
            print(f"\n  [WARNING] {error_msg}")
            return error_msg
    
    def dynamic_llm_analysis(self, dockerfile_content: str) -> Dict[str, Any]:
        system_prompt = """You are an expert Docker and container specialist focused ONLY on image size optimization. Your role is to analyze Dockerfiles for:
        1. Image size reduction opportunities
        2. Layer optimization techniques
        3. Cache optimization for smaller images
        4. Multi-stage build opportunities
        5. Unnecessary files and dependencies that can be removed
        
        IGNORE: security issues, performance (non-size), maintainability, best practices (non-size), runtime concerns.
        FOCUS ONLY: on techniques that reduce the final Docker image size.
        
        Provide structured, actionable insights focused ONLY on size reduction."""
        
        # Skip knowledge base context for size-only analysis
        kb_context = ""
                
        user_prompt = f"""Analyze this Dockerfile and identify ONLY size-related optimization opportunities. IGNORE security, performance (non-size), maintainability, and other concerns.

Dockerfile:
```
{dockerfile_content}
```

Return JSON with this structure (ONLY size-related fields):
{{
    "performance_issues": ["list of size-related performance problems (e.g., unnecessary layers, large files, unused packages)"],
    "optimization_opportunities": ["size optimization suggestions (e.g., multi-stage builds, removing build dependencies, combining layers)"],
    "estimated_wasted_space_kb": <number>,
    "overall_assessment": "summary of size optimization opportunities",
    "recommendations": [
      {{
        "category": "optimization",
        "severity": "high|medium|low",
        "message": "specific actionable size optimization recommendation with exact fix",
        "instruction_line": <line number or null>
      }}
    ]
}}

CRITICAL RULES:
- ONLY include size-related issues (image size, layer count, cache size, wasted space)
- IGNORE security risks, maintainability, runtime concerns, best practices (unless size-related)
- Each recommendation MUST be SPECIFIC and ACTIONABLE for size reduction
- Focus on: layer reduction, cache cleanup, multi-stage builds, removing unnecessary files/dependencies

Examples of GOOD size-related recommendations:
- "Combine apt-get update and apt-get install into a single RUN command to reduce layers" (line 5)
- "Add --no-install-recommends flag to apt-get install to reduce image size by ~50MB" (line 6)
- "Add 'apt-get clean && rm -rf /var/lib/apt/lists/*' after package installation to clean apt cache" (line 6)
- "Use multi-stage build to separate build dependencies from runtime image" (line 1)
- "Remove unnecessary build tools in final stage to reduce image size" (line 20)

Examples of BAD recommendations (not size-focused):
- "Add USER directive for security" (security, not size)
- "Use specific version tag for reproducibility" (maintainability, not size)
- "Add HEALTHCHECK" (best practice, not size)

Focus ONLY on identifying size optimization opportunities and providing SPECIFIC, ACTIONABLE recommendations for reducing image size."""
        
        response = self._call_llm(user_prompt, system_prompt)
        
        if response.startswith("LLM API error:") or response.startswith("Error:"):
            return {
                "success": False,
                "data": {
                    "overall_assessment": f"API Error: {response}",
                    "performance_issues": [],
                    "optimization_opportunities": [],
                    "estimated_wasted_space_kb": 0,
                    "recommendations": []
                },
                "raw_response": response,
                "error": response
            }
        
        if not response or len(response.strip()) == 0:
            print(f"\n  [WARNING] Empty LLM response")
            response = "{}"
        
        try:
            cleaned_response = response.strip()
            
            if "```json" in cleaned_response:
                json_start = cleaned_response.find("```json") + 7
                json_end = cleaned_response.find("```", json_start)
                if json_end != -1:
                    cleaned_response = cleaned_response[json_start:json_end].strip()
            elif "```" in cleaned_response:
                json_start = cleaned_response.find("```") + 3
                json_end = cleaned_response.find("```", json_start)
                if json_end != -1:
                    cleaned_response = cleaned_response[json_start:json_end].strip()
            
            if cleaned_response.startswith("{"):
                brace_count = 0
                json_end_pos = -1
                for i, char in enumerate(cleaned_response):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end_pos = i + 1
                            break
                
                if json_end_pos > 0:
                    cleaned_response = cleaned_response[:json_end_pos]
                elif json_end_pos == -1 and brace_count > 0:
                    cleaned_response += "\n" + "}" * brace_count
                    bracket_count = cleaned_response.count('[') - cleaned_response.count(']')
                    if bracket_count > 0:
                        cleaned_response = cleaned_response.rstrip('}') + "]" * bracket_count + "}"
            
            llm_data = json.loads(cleaned_response)
            
            # Filter to only size-related issues
            performance_issues = llm_data.get("performance_issues", [])
            optimization_opportunities = llm_data.get("optimization_opportunities", [])
            
            # Filter performance issues to only size-related ones
            SIZE_KEYWORDS = (
                "size", "layer", "cache", "no-cache", "multi-stage",
                "apt-get clean", "rm -rf /var/lib/apt/lists",
                "--no-install-recommends", "--no-cache-dir", "COPY", "ADD",
                "reduce", "smaller", "minimize", "compress", "waste", "unnecessary"
            )
            
            size_performance_issues = [
                issue for issue in performance_issues 
                if any(keyword in str(issue).lower() for keyword in SIZE_KEYWORDS)
            ]
            
            size_optimization_opportunities = [
                opt for opt in optimization_opportunities 
                if any(keyword in str(opt).lower() for keyword in SIZE_KEYWORDS)
            ]
            
            # Filter recommendations to only size-related
            all_recommendations = llm_data.get("recommendations", [])
            size_recommendations = [
                rec for rec in all_recommendations
                if rec.get("category") == "optimization" or 
                   any(keyword in str(rec.get("message", "")).lower() for keyword in SIZE_KEYWORDS)
            ]
            
            performance_issues_count = len(size_performance_issues)
            optimization_count = len(size_optimization_opportunities)
            
            print(f"\n  [LLM Response Analysis (Size-Only)]", flush=True)
            print(f"    Raw response length: {len(response)} chars", flush=True)
            print(f"    Size issues found: {performance_issues_count} size-related performance issues, {optimization_count} size optimization opportunities", flush=True)
            
            result = {
                "success": True,
                "data": {
                    "performance_issues": size_performance_issues,
                    "optimization_opportunities": size_optimization_opportunities,
                    "estimated_wasted_space_kb": llm_data.get("estimated_wasted_space_kb", 0),
                    "overall_assessment": llm_data.get("overall_assessment", "Size analysis completed"),
                    "recommendations": size_recommendations
                },
                "raw_response": response
            }
            return result
        except json.JSONDecodeError as e:
            try:
                partial_data = {}
                
                if '"performance_issues"' in response:
                    perf_start = response.find('"performance_issues"')
                    if perf_start != -1:
                        array_start = response.find('[', perf_start)
                        if array_start != -1:
                            bracket_count = 0
                            array_end = array_start
                            for i in range(array_start, min(len(response), array_start + 2000)):
                                if response[i] == '[':
                                    bracket_count += 1
                                elif response[i] == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        array_end = i + 1
                                        break
                            if array_end > array_start:
                                try:
                                    perf_array = json.loads(response[array_start:array_end])
                                    partial_data["performance_issues"] = perf_array
                                except:
                                    pass
                
                if partial_data:
                    return {
                        "success": True,
                        "data": {
                            "performance_issues": partial_data.get("performance_issues", []),
                            "optimization_opportunities": [],
                            "estimated_wasted_space_kb": 0,
                            "overall_assessment": "Partial size analysis - JSON response was incomplete",
                            "recommendations": []
                        },
                        "raw_response": response,
                        "warning": "Partial JSON parsing - some fields may be missing"
                    }
            except:
                pass
            
            print(f"\n  [WARNING] JSON parsing failed. Response preview (first 500 chars):")
            print(f"      {response[:500]}")
            
            return {
                "success": False,
                "data": {
                    "overall_assessment": f"Size analysis unavailable - JSON parsing failed. Response may be incomplete.",
                    "performance_issues": [],
                    "optimization_opportunities": [],
                    "estimated_wasted_space_kb": 0,
                    "recommendations": []
                },
                "raw_response": response,
                "error": f"JSON parsing error: {str(e)}"
            }
    
    def analyze_dockerfile(self, dockerfile_path: str) -> Dict[str, Any]:
        try:
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                dockerfile_content = f.read()
        except FileNotFoundError:
            return {
                "error": f"Dockerfile not found: {dockerfile_path}",
                "scores": {}
            }
        
        # Skip base image analysis for size-only analysis
        base_image_issues: List[Dict[str, Any]] = []

        print(f"  Performing LLM analysis...", end="", flush=True)
        llm_analysis = self.dynamic_llm_analysis(dockerfile_content)
        
        if llm_analysis.get("success"):
            raw_response = llm_analysis.get("raw_response", "")
            print(f"\n  [LLM Response] Length: {len(raw_response)} chars", flush=True)
            if raw_response:
                preview = raw_response[:300].replace('\n', ' ')
                print(f"  [LLM Response Preview] {preview}...", flush=True)
            
            llm_data = llm_analysis.get("data", {})
            print(f"  [LLM Parsed Data (Size-Only)] Performance Issues: {len(llm_data.get('performance_issues', []))}, "
                  f"Optimization Opportunities: {len(llm_data.get('optimization_opportunities', []))}", flush=True)
        else:
            error = llm_analysis.get("error", "Unknown error")
            print(f"\n  [LLM Analysis Failed] {error[:200]}")
        
        llm_data = llm_analysis.get("data", {})
        performance_issues = llm_data.get("performance_issues", [])
        optimization_opportunities = llm_data.get("optimization_opportunities", [])
        llm_wasted_space = llm_data.get("estimated_wasted_space_kb", 0)
        
        performance_issues_count = len(performance_issues)
        optimization_count = len(optimization_opportunities)
        
        # Calculate size efficiency score based on wasted space and issues
        if llm_wasted_space > 0:
            # More wasted space = lower score
            efficiency_score = max(0, 100 - (llm_wasted_space / 100))  # Scale: 10MB wasted = 10% reduction
        else:
            efficiency_score = 100.0 if performance_issues_count == 0 else max(0, 100 - (performance_issues_count * 10))
        
        # Overall score is just the efficiency score for size-only analysis
        overall_score = efficiency_score
        
        scores = {
            "overall_score": round(overall_score, 1),
            "efficiency_score": round(efficiency_score, 1),
            "estimated_wasted_space_kb": round(llm_wasted_space if llm_wasted_space is not None and isinstance(llm_wasted_space, (int, float)) else 0, 2)
        }
        
        print(f"  [Size Issues Found] Performance Issues: {performance_issues_count}, Optimization Opportunities: {optimization_count}")
        print(f"  [Calculated Scores] Overall: {scores['overall_score']}%, "
              f"Efficiency: {scores['efficiency_score']}%, "
              f"Wasted Space: {scores['estimated_wasted_space_kb']:.2f} KB")
        
        return {
            "dockerfile_path": dockerfile_path,
            "llm_analysis": llm_analysis,
            "scores": scores,
            "base_image_issues": base_image_issues
        }
    
    def print_analysis_report(self, analysis_result: Dict[str, Any]) -> None:
        if "error" in analysis_result:
            print(f"  ERROR: {analysis_result['error']}")
            return
        
        scores = analysis_result.get("scores", {})
        llm_analysis = analysis_result.get("llm_analysis")
        
        has_api_error = llm_analysis and not llm_analysis.get("success") and llm_analysis.get("error")
        
        print("\n" + "="*60)
        print("DOCKERFILE SIZE ANALYSIS REPORT (LLM-Based)")
        print("="*60)
        
        if has_api_error:
            print(f"\n[WARNING] NOTE: Scores are default values due to API error.")
            print(f"    Real analysis requires a valid API key with available quota.")
        
        print(f"\nSIZE-RELATED SCORES:")
        print(f"  Overall Size Efficiency Score: {scores.get('overall_score', 0):.1f}%")
        print(f"  Efficiency Score:              {scores.get('efficiency_score', 0):.1f}%")
        
        if "estimated_wasted_space_kb" in scores:
            wasted = scores["estimated_wasted_space_kb"]
            print(f"  Potential Wasted Space:       {wasted:.2f} kB")
        
        if llm_analysis and llm_analysis.get("success"):
            llm_data = llm_analysis.get("data", {})
            
            print(f"\nLLM SIZE ANALYSIS:")
            
            recommendations = llm_data.get("recommendations", [])
            if recommendations:
                print(f"\n  Size Optimization Recommendations ({len(recommendations)}):")
                for rec in recommendations[:10]:  # Top 10
                    severity = rec.get("severity", "medium").upper()
                    message = rec.get("message", "")
                    line = rec.get("instruction_line")
                    line_str = f" (line {line})" if line else ""
                    print(f"    [{severity:8}] {message}{line_str}")
            
            performance_issues = llm_data.get("performance_issues", [])
            if performance_issues:
                print(f"\n  Size-Related Performance Issues ({len(performance_issues)}):")
                for issue in performance_issues[:5]:
                    print(f"    [SIZE] {issue}")
            
            optimizations = llm_data.get("optimization_opportunities", [])
            if optimizations:
                print(f"\n  Size Optimization Opportunities ({len(optimizations)}):")
                for opt in optimizations[:5]:
                    print(f"    [OPT] {opt}")
            
            assessment = llm_data.get("overall_assessment", "")
            if assessment:
                print(f"\n  Size Assessment:")
                print(f"    {assessment}")
        
        elif llm_analysis:
            error_msg = llm_analysis.get("error", "")
            if error_msg:
                print(f"\n[ERROR] LLM API ERROR:")
                if "429" in error_msg or "quota" in error_msg.lower() or "insufficient_quota" in error_msg.lower():
                    print(f"    [WARNING] API Quota Exceeded")
                    print(f"    Your API key has exceeded its quota.")
                    print(f"    Please check your billing and plan.")
                elif "403" in error_msg and "moderation" in error_msg.lower():
                    print(f"    [WARNING] Content Moderation Blocked")
                    print(f"    The model's moderation system flagged the prompt.")
                    print(f"    Try using a different model: --model 'meta-llama/llama-3.2-3b-instruct:free'")
                    print(f"    Or use: --model 'google/gemini-flash-1.5-8b:free'")
                elif "401" in error_msg or "invalid" in error_msg.lower():
                    print(f"    [WARNING] Invalid API Key")
                    print(f"    Please check your API key is correct.")
                else:
                    print(f"    {error_msg[:200]}")
            else:
                assessment = llm_analysis.get('data', {}).get('overall_assessment', 'Analysis unavailable')
                print(f"\n[WARNING] LLM Analysis Issues:")
                print(f"    {assessment}")
        
        print("\n" + "="*60 + "\n")


def find_dockerfiles(repo_path: str) -> List[str]:
    matches = []
    for root, _dirs, files in os.walk(repo_path):
        for name in files:
            lname = name.lower()
            if lname == "dockerfile" or lname.startswith("dockerfile."):
                matches.append(os.path.join(root, name))
    return matches

