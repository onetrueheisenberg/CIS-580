import os
import sys
from typing import Dict, List, Optional, Any
        
class DockerfileFixer:    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        try:
            from .dockerfile_llm_analyzer import DockerfileAnalyzer
        except ImportError:
            from dockerfile_llm_analyzer import DockerfileAnalyzer
        
        self.analyzer = DockerfileAnalyzer(
            api_key=api_key,
            model=model
        )
        self.api_key = self.analyzer.api_key
        self.model = self.analyzer.model
    
    def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return self.analyzer._call_llm(prompt, system_prompt)
    
    def fix_dockerfile(
        self,
        original_dockerfile: str,
        analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not original_dockerfile or not original_dockerfile.strip():
            return {
                "success": False,
                "error": "Empty Dockerfile provided",
                "fixed_dockerfile": original_dockerfile
            }
        
        if not analysis_results:
            return {
                "success": False,
                "error": "No analysis results provided",
                "fixed_dockerfile": original_dockerfile
            }
        
        llm_analysis = analysis_results.get("llm_analysis", {})
        if not llm_analysis or not llm_analysis.get("success"):
            error_msg = llm_analysis.get("error", "Invalid analysis results")
            return {
                "success": False,
                "error": f"Invalid analysis results: {error_msg}",
                "fixed_dockerfile": original_dockerfile
            }
        
        llm_data = llm_analysis.get("data", {})
        scores = analysis_results.get("scores", {})
        
        security_risks = llm_data.get("security_risks", [])
        performance_issues = llm_data.get("performance_issues", [])
        optimization_opps = llm_data.get("optimization_opportunities", [])
        missing_practices = llm_data.get("best_practices_missing", [])
        recommendations = llm_data.get("recommendations", [])
        
        system_prompt = """You are a conservative Docker optimization specialist. Your goal is to fix ONLY the issues found in the analysis, without introducing new problems.

CRITICAL RULES:
1. Fix ONLY the issues listed in the analysis - do not add new features
2. Do NOT introduce new security risks, performance issues, or complexity
3. Preserve ALL original functionality - the Dockerfile must work exactly as before
4. Make minimal changes - if something works, don't change it
5. Do NOT add best practices that weren't in the missing practices list
6. Do NOT change base images unless there's a critical security issue
7. Do NOT add multi-stage builds unless explicitly needed for a critical issue
8. Do NOT add USER directives unless running as root is a CRITICAL security risk
9. Keep the same package versions and installation methods when possible
10. Preserve comments and structure that help maintainability

Your job is to fix what's broken, not to redesign the Dockerfile."""
        
        analysis_summary = f"""ANALYSIS RESULTS:

Security Score: {scores.get('security_score', 50)}/100
Efficiency Score: {scores.get('efficiency_score', 50)}/100
Best Practices Score: {scores.get('best_practices_score', 50)}/100
Overall Score: {scores.get('overall_score', 50)}/100

SECURITY RISKS ({len(security_risks)}):
"""
        for i, risk in enumerate(security_risks[:10], 1):
            analysis_summary += f"{i}. {risk}\n"
        
        analysis_summary += f"\nPERFORMANCE ISSUES ({len(performance_issues)}):\n"
        for i, issue in enumerate(performance_issues[:10], 1):
            analysis_summary += f"{i}. {issue}\n"
        
        analysis_summary += f"\nOPTIMIZATION OPPORTUNITIES ({len(optimization_opps)}):\n"
        for i, opp in enumerate(optimization_opps[:10], 1):
            analysis_summary += f"{i}. {opp}\n"
        
        analysis_summary += f"\nMISSING BEST PRACTICES ({len(missing_practices)}):\n"
        for i, practice in enumerate(missing_practices[:10], 1):
            analysis_summary += f"{i}. {practice}\n"
        
        if recommendations:
            analysis_summary += f"\nSPECIFIC RECOMMENDATIONS ({len(recommendations)}):\n"
            for rec in recommendations[:15]:
                category = rec.get("category", "general")
                severity = rec.get("severity", "medium")
                message = rec.get("message", "")
                line = rec.get("instruction_line")
                line_str = f" (line {line})" if line else ""
                analysis_summary += f"- [{severity.upper()}] {category}: {message}{line_str}\n"
        
        user_prompt = f"""Fix ONLY the issues found in the analysis. Do NOT add new features or introduce new problems.

ORIGINAL DOCKERFILE:
```
{original_dockerfile}
```

{analysis_summary}

FIXING RULES (in priority order):
1. Fix ONLY the security risks listed above - do not add new security measures
2. Fix ONLY the performance issues listed above - do not optimize things that aren't broken
3. Implement ONLY the optimization opportunities listed above - skip minor ones
4. Add ONLY the missing best practices listed above - do not add others
5. Fix runtime concerns ONLY if they would cause failures

CRITICAL CONSTRAINTS:
- DO NOT change base images unless there's a critical security vulnerability
- DO NOT add USER directives unless the analysis explicitly says running as root is a CRITICAL risk
- DO NOT add multi-stage builds unless explicitly needed
- DO NOT add HEALTHCHECK unless the analysis specifically recommends it
- DO NOT change package versions unless there's a security issue
- DO NOT add new packages or tools unless needed to fix a listed issue
- DO NOT remove functionality that works
- DO NOT change working commands unless they have a listed issue
- PRESERVE all original functionality and behavior
- KEEP the same structure and style

WHAT TO DO:
- Fix the specific issues listed in the analysis
- Combine RUN commands only if it fixes a listed performance issue
- Clean up apt cache only if it fixes a listed issue
- Add missing practices ONLY from the list above

WHAT NOT TO DO:
- Do NOT add features not in the analysis
- Do NOT "improve" things that aren't broken
- Do NOT make the Dockerfile more complex
- Do NOT introduce new security risks, performance issues, or missing practices

Return ONLY the fixed Dockerfile. No explanations, no markdown, no code blocks. Just the raw Dockerfile starting with FROM."""
        
        print(f"  Generating optimized Dockerfile...", end="", flush=True)
        response = self._call_llm(user_prompt, system_prompt)
        print(" Done")
        
        if response and not response.startswith("Error:"):
            print(f"\n  [LLM Fix Response] Length: {len(response)} chars")
            preview = response[:300].replace('\n', ' ')
            print(f"  [LLM Fix Preview] {preview}...")
        else:
            print(f"\n  [LLM Fix Failed] {response[:200] if response else 'No response'}")
        
        fixed_dockerfile = self._extract_dockerfile(response)
        
        if fixed_dockerfile:
            original_lines = len(original_dockerfile.split('\n'))
            fixed_lines = len(fixed_dockerfile.split('\n'))
            print(f"  [Dockerfile Extracted] Original: {original_lines} lines, Fixed: {fixed_lines} lines")
            if fixed_dockerfile == original_dockerfile:
                print(f"  [Warning] Fixed Dockerfile is identical to original")
        else:
            print(f"  [Error] Failed to extract Dockerfile from LLM response")
        
        if not fixed_dockerfile or fixed_dockerfile == original_dockerfile:
            return {
                "success": False,
                "error": "Failed to generate optimized Dockerfile or no changes made",
                "fixed_dockerfile": original_dockerfile,
                "raw_response": response
            }
        
        return {
            "success": True,
            "fixed_dockerfile": fixed_dockerfile,
            "original_dockerfile": original_dockerfile,
            "raw_response": response
        }
    
    def _extract_dockerfile(self, response: str) -> str:
        if not response or response.startswith("Error:"):
            return ""
        
        cleaned = response.strip()
        
        while "```" in cleaned:
            start = cleaned.find("```")
            if start == -1:
                break
            end = cleaned.find("```", start + 3)
            if end == -1:
                cleaned = cleaned[:start].strip()
                break
            cleaned = cleaned[:start] + cleaned[start+3:end] + cleaned[end+3:]
            cleaned = cleaned.strip()
        
        cleaned = cleaned.replace("```", "").strip()
        
        lines = cleaned.split('\n')
        dockerfile_lines = []
        found_from = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                if found_from:
                    dockerfile_lines.append(line)
                continue
            
            if stripped.upper().startswith("FROM"):
                found_from = True
                dockerfile_lines.append(line)
            elif found_from:
                if not stripped.startswith('```') and '```' not in stripped:
                    dockerfile_lines.append(line)
        
        if not found_from:
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('```') or '```' in stripped:
                    continue
                if any(keyword in stripped.upper() for keyword in ["FROM", "RUN", "COPY", "ADD", "WORKDIR"]):
                    dockerfile_lines.append(line)
        
        result = '\n'.join(dockerfile_lines) if dockerfile_lines else cleaned
        
        result = result.replace('```', '').strip()
        
        return result





