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

class DockerfileAnalyzer:    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
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
    
    def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
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
        system_prompt = """You are an expert Docker and container specialist. Your role is to help improve Dockerfile quality by analyzing:
        1. Dockerfile structure and best practices
        2. Performance and efficiency improvements
        3. Optimization opportunities
        4. Code quality and maintainability
        5. Image size reduction techniques
        6. Build process improvements

        Provide structured, actionable insights to help developers create better Dockerfiles.
        Focus on practical recommendations and real-world improvements."""
                
        user_prompt = f"""Analyze this Dockerfile and identify issues. Return JSON with the issues you find.

Dockerfile:
```
{dockerfile_content}
```

Return JSON with this structure:
{{
    "security_risks": ["list of security concerns"],
    "performance_issues": ["list of performance problems"],
    "optimization_opportunities": ["optimization suggestions"],
    "runtime_concerns": ["runtime problems"],
    "best_practices_missing": ["missing best practices"],
    "estimated_wasted_space_kb": <number>,
    "complexity_score": <1-10, where 10 is most complex>,
    "maintainability_score": <1-10, where 10 is most maintainable>,
    "overall_assessment": "summary of Dockerfile quality",
    "recommendations": [{{"category": "security|performance|best_practice|optimization", "severity": "critical|high|medium|low", "message": "specific recommendation", "instruction_line": <line number or null>}}]
}}

Focus on identifying issues accurately. Do not calculate scores - just list the issues you find."""
        
        response = self._call_llm(user_prompt, system_prompt)
        
        if response.startswith("LLM API error:") or response.startswith("Error:"):
            return {
                "success": False,
                "data": {
                    "overall_assessment": f"API Error: {response}",
                    "security_risks": [],
                    "performance_issues": [],
                    "optimization_opportunities": [],
                    "runtime_concerns": [],
                    "best_practices_missing": [],
                    "estimated_wasted_space_kb": 0,
                    "complexity_score": 5,
                    "maintainability_score": 5,
                    "security_score": 50,
                    "efficiency_score": 50,
                    "best_practices_score": 50,
                    "overall_score": 50,
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
            
            security_risks_count = len(llm_data.get("security_risks", []))
            performance_issues_count = len(llm_data.get("performance_issues", []))
            missing_practices_count = len(llm_data.get("best_practices_missing", []))
            
            print(f"\n  [LLM Response Analysis]", flush=True)
            print(f"    Raw response length: {len(response)} chars", flush=True)
            print(f"    Issues found: {security_risks_count} security risks, {performance_issues_count} performance issues, {missing_practices_count} missing practices", flush=True)
            
            result = {
                "success": True,
                "data": {
                    "security_risks": llm_data.get("security_risks", []),
                    "performance_issues": llm_data.get("performance_issues", []),
                    "optimization_opportunities": llm_data.get("optimization_opportunities", []),
                    "runtime_concerns": llm_data.get("runtime_concerns", []),
                    "best_practices_missing": llm_data.get("best_practices_missing", []),
                    "estimated_wasted_space_kb": llm_data.get("estimated_wasted_space_kb", 0),
                    "complexity_score": llm_data.get("complexity_score", 5),
                    "maintainability_score": llm_data.get("maintainability_score", 5),
                    "overall_assessment": llm_data.get("overall_assessment", "Analysis completed"),
                    "recommendations": llm_data.get("recommendations", [])
                },
                "raw_response": response
            }
            return result
        except json.JSONDecodeError as e:
            try:
                partial_data = {}
                
                if '"security_risks"' in response:
                    risks_start = response.find('"security_risks"')
                    if risks_start != -1:
                        array_start = response.find('[', risks_start)
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
                                    risks_array = json.loads(response[array_start:array_end])
                                    partial_data["security_risks"] = risks_array
                                except:
                                    pass
                
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
                            "security_risks": partial_data.get("security_risks", []),
                            "performance_issues": partial_data.get("performance_issues", []),
                            "optimization_opportunities": [],
                            "runtime_concerns": [],
                            "best_practices_missing": [],
                            "estimated_wasted_space_kb": 0,
                            "complexity_score": 5,
                            "maintainability_score": 5,
                            "security_score": 50,
                            "efficiency_score": 50,
                            "best_practices_score": 50,
                            "overall_score": 50,
                            "overall_assessment": "Partial analysis - JSON response was incomplete",
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
                    "overall_assessment": f"Analysis unavailable - JSON parsing failed. Response may be incomplete.",
                    "security_risks": [],
                    "performance_issues": [],
                    "optimization_opportunities": [],
                    "runtime_concerns": [],
                    "best_practices_missing": [],
                    "estimated_wasted_space_kb": 0,
                    "complexity_score": 5,
                    "maintainability_score": 5,
                    "security_score": 50,
                    "efficiency_score": 50,
                    "best_practices_score": 50,
                    "overall_score": 50,
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
        
        print(f"  Performing LLM analysis...", end="", flush=True)
        llm_analysis = self.dynamic_llm_analysis(dockerfile_content)
        
        if llm_analysis.get("success"):
            raw_response = llm_analysis.get("raw_response", "")
            print(f"\n  [LLM Response] Length: {len(raw_response)} chars", flush=True)
            if raw_response:
                preview = raw_response[:300].replace('\n', ' ')
                print(f"  [LLM Response Preview] {preview}...", flush=True)
            
            llm_data = llm_analysis.get("data", {})
            print(f"  [LLM Parsed Data] Security Risks: {len(llm_data.get('security_risks', []))}, "
                  f"Performance Issues: {len(llm_data.get('performance_issues', []))}, "
                  f"Optimization Opportunities: {len(llm_data.get('optimization_opportunities', []))}", flush=True)
        else:
            error = llm_analysis.get("error", "Unknown error")
            print(f"\n  [LLM Analysis Failed] {error[:200]}")
        
        llm_data = llm_analysis.get("data", {})
        security_risks = llm_data.get("security_risks", [])
        performance_issues = llm_data.get("performance_issues", [])
        missing_practices = llm_data.get("best_practices_missing", [])
        llm_complexity = llm_data.get("complexity_score")
        llm_maintainability = llm_data.get("maintainability_score")
        llm_wasted_space = llm_data.get("estimated_wasted_space_kb")
        
        security_risks_count = len(security_risks)
        performance_issues_count = len(performance_issues)
        missing_practices_count = len(missing_practices)
        
        # Security: 100 - (risks * 12), minimum 0
        security_score = 100.0 if security_risks_count == 0 else max(0, 100 - (security_risks_count * 12))
        
        # Efficiency: 100 - (performance_issues * 9), minimum 0
        efficiency_score = 100.0 if performance_issues_count == 0 else max(0, 100 - (performance_issues_count * 9))
        
        # Best Practices: 100 - (missing_practices * 12), minimum 0
        best_practices_score = 100.0 if missing_practices_count == 0 else max(0, 100 - (missing_practices_count * 12))
        
        # Overall: weighted average
        overall_score = (security_score * 0.3) + (efficiency_score * 0.4) + (best_practices_score * 0.3)
        
        scores = {
            "overall_score": round(overall_score, 1),
            "efficiency_score": round(efficiency_score, 1),
            "security_score": round(security_score, 1),
            "best_practices_score": round(best_practices_score, 1),
            "complexity_score": round(llm_complexity if llm_complexity is not None and isinstance(llm_complexity, (int, float)) else 5.0, 1),
            "maintainability_score": round(llm_maintainability if llm_maintainability is not None and isinstance(llm_maintainability, (int, float)) else 5.0, 1),
            "estimated_wasted_space_kb": round(llm_wasted_space if llm_wasted_space is not None and isinstance(llm_wasted_space, (int, float)) else 0, 2)
        }
        
        print(f"  [Issues Found] Security Risks: {security_risks_count}, Performance Issues: {performance_issues_count}, Missing Practices: {missing_practices_count}")
        print(f"  [Calculated Scores] Overall: {scores['overall_score']}%, "
              f"Security: {scores['security_score']}%, "
              f"Efficiency: {scores['efficiency_score']}%, "
              f"Best Practices: {scores['best_practices_score']}%")
        
        return {
            "dockerfile_path": dockerfile_path,
            "llm_analysis": llm_analysis,
            "scores": scores
        }
    
    def print_analysis_report(self, analysis_result: Dict[str, Any]) -> None:
        if "error" in analysis_result:
            print(f"  ERROR: {analysis_result['error']}")
            return
        
        scores = analysis_result.get("scores", {})
        llm_analysis = analysis_result.get("llm_analysis")
        
        has_api_error = llm_analysis and not llm_analysis.get("success") and llm_analysis.get("error")
        
        print("\n" + "="*60)
        print("DOCKERFILE ANALYSIS REPORT (LLM-Based)")
        print("="*60)
        
        if has_api_error:
            print(f"\n[WARNING] NOTE: Scores are default values due to API error.")
            print(f"    Real analysis requires a valid API key with available quota.")
        
        print(f"\nSCORES:")
        print(f"  Image Efficiency Score: {scores.get('overall_score', 0):.1f}%")
        print(f"  Security Score:          {scores.get('security_score', 0):.1f}%")
        print(f"  Best Practices Score:    {scores.get('best_practices_score', 0):.1f}%")
        print(f"  Efficiency Score:       {scores.get('efficiency_score', 0):.1f}%")
        print(f"  Complexity Score:        {scores.get('complexity_score', 0):.1f}/10")
        print(f"  Maintainability Score:   {scores.get('maintainability_score', 0):.1f}/10")
        
        if "estimated_wasted_space_kb" in scores:
            wasted = scores["estimated_wasted_space_kb"]
            print(f"  Potential Wasted Space:  {wasted:.2f} kB")
        
        if llm_analysis and llm_analysis.get("success"):
            llm_data = llm_analysis.get("data", {})
            
            print(f"\nLLM DYNAMIC ANALYSIS:")
            
            recommendations = llm_data.get("recommendations", [])
            if recommendations:
                by_category = {}
                for rec in recommendations:
                    cat = rec.get("category", "general")
                    if cat not in by_category:
                        by_category[cat] = []
                    by_category[cat].append(rec)
                
                for category in ["security", "performance", "best_practice", "optimization"]:
                    if category in by_category:
                        print(f"\n  {category.upper()} Recommendations ({len(by_category[category])}):")
                        for rec in by_category[category][:5]:  # Top 5 per category
                            severity = rec.get("severity", "medium").upper()
                            message = rec.get("message", "")
                            line = rec.get("instruction_line")
                            line_str = f" (line {line})" if line else ""
                            print(f"    [{severity:8}] {message}{line_str}")
            
            security_risks = llm_data.get("security_risks", [])
            if security_risks:
                print(f"\n  Security Risks ({len(security_risks)}):")
                for risk in security_risks[:5]:  # Top 5
                    print(f"    [-] {risk}")
            
            performance_issues = llm_data.get("performance_issues", [])
            if performance_issues:
                print(f"\n  Performance Issues ({len(performance_issues)}):")
                for issue in performance_issues[:5]:
                    print(f"    [PERF] {issue}")
            
            optimizations = llm_data.get("optimization_opportunities", [])
            if optimizations:
                print(f"\n  Optimization Opportunities ({len(optimizations)}):")
                for opt in optimizations[:5]:
                    print(f"    [OPT] {opt}")
            
            runtime_concerns = llm_data.get("runtime_concerns", [])
            if runtime_concerns:
                print(f"\n  Runtime Concerns ({len(runtime_concerns)}):")
                for concern in runtime_concerns[:5]:
                    print(f"    [RUNTIME] {concern}")
            
            missing_practices = llm_data.get("best_practices_missing", [])
            if missing_practices:
                print(f"\n  Missing Best Practices ({len(missing_practices)}):")
                for practice in missing_practices[:5]:
                    print(f"    [MISSING] {practice}")
            
            assessment = llm_data.get("overall_assessment", "")
            if assessment:
                print(f"\n  Overall Assessment:")
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

