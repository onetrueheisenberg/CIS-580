import os
import sys
from typing import Dict, List, Optional, Any, Tuple
        
class DockerfileFixer:    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_knowledge_base: bool = True
    ):
        try:
            from .dockerfile_llm_analyzer import DockerfileAnalyzer
        except ImportError:
            from dockerfile_llm_analyzer import DockerfileAnalyzer
        
        self.analyzer = DockerfileAnalyzer(
            api_key=api_key,
            model=model,
            use_knowledge_base=use_knowledge_base
        )
        self.api_key = self.analyzer.api_key
        self.model = self.analyzer.model
        self.use_knowledge_base = use_knowledge_base
        self.knowledge_base = self.analyzer.knowledge_base if hasattr(self.analyzer, 'knowledge_base') else None
    
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
        
        dockerfile_for_fixing = original_dockerfile
        auto_base_image_changes: List[Dict[str, str]] = []
        if self.use_knowledge_base and self.knowledge_base:
            try:
                dockerfile_for_fixing, auto_base_image_changes = self._auto_fix_base_images(
                    dockerfile_for_fixing
                )
                if auto_base_image_changes:
                    print("  [KB] Applied deterministic base image fixes:")
                    for change in auto_base_image_changes:
                        print(
                            f"    FROM {change['original']}  →  {change['replacement']} "
                            f"(reason: {change.get('reason', 'knowledge base recommendation')})"
                        )
            except Exception as e:
                print(f"  [WARNING] Failed to apply KB base image fixes: {e}")

        llm_data = llm_analysis.get("data", {})
        scores = analysis_results.get("scores", {})
        
        security_risks = llm_data.get("security_risks", [])
        performance_issues = llm_data.get("performance_issues", [])
        optimization_opps = llm_data.get("optimization_opportunities", [])
        missing_practices = llm_data.get("best_practices_missing", [])
        recommendations = llm_data.get("recommendations", [])
        
        overall_score = scores.get("overall_score", 0)
        security_score = scores.get("security_score", 0)
        efficiency_score = scores.get("efficiency_score", 0)
        best_practices_score = scores.get("best_practices_score", 0)
        
        critical_issues = len(security_risks)
        high_severity_recommendations = [
            r for r in recommendations 
            if r.get("severity", "low") in ["critical", "high"]
        ]
        critical_issues += len(high_severity_recommendations)
        
        is_already_excellent = (
            overall_score >= 95.0 and
            security_score >= 95.0 and
            efficiency_score >= 85.0 and
            best_practices_score >= 95.0 and
            critical_issues == 0 and
            len(security_risks) == 0 and
            len(performance_issues) <= 1
        )
        
        if is_already_excellent:
            print(f"  [Skipping Fix] Dockerfile is already excellent (Overall: {overall_score}%, "
                  f"Security: {security_score}%, Efficiency: {efficiency_score}%, "
                  f"Issues: {len(security_risks)} security, {len(performance_issues)} performance)")
            return {
                "success": True,
                "fixed_dockerfile": original_dockerfile,
                "original_dockerfile": original_dockerfile,
                "skipped": True,
                "reason": f"Dockerfile already excellent (Overall: {overall_score}%, "
                         f"Security: {security_score}%, Efficiency: {efficiency_score}%)",
                "raw_response": "No changes needed - Dockerfile is already optimal"
            }
        
        has_actionable_issues = (
            len(security_risks) > 0 or
            len(performance_issues) > 1 or
            len(missing_practices) > 0 or
            len(high_severity_recommendations) > 0
        )
        
        if not has_actionable_issues and overall_score >= 90.0:
            print(f"[Skipping Fix] No actionable issues found (Overall: {overall_score}%)")
            return {
                "success": True,
                "fixed_dockerfile": original_dockerfile,
                "original_dockerfile": original_dockerfile,
                "skipped": True,
                "reason": f"No actionable issues to fix (Overall: {overall_score}%)",
                "raw_response": "No changes needed - no actionable issues found"
            }
        
        system_prompt = f"""You are a precise Docker optimization specialist. Your goal is to fix ONLY the specific issues identified in the analysis, using the recommendations as your primary guide.

CURRENT DOCKERFILE STATUS:
- Overall Score: {overall_score}%
- Security Score: {security_score}%
- Efficiency Score: {efficiency_score}%
- Best Practices Score: {best_practices_score}%
- Security Risks: {len(security_risks)}
- Performance Issues: {len(performance_issues)}
- Missing Practices: {len(missing_practices)}

CRITICAL RULES:
1. Use the SPECIFIC RECOMMENDATIONS as your PRIMARY source for fixes - they contain exact instructions
2. For each recommendation, make the exact change it suggests at the specified line
3. Do NOT introduce new security risks, performance issues, or complexity
4. Preserve ALL original functionality - the Dockerfile must work exactly as before
5. Make targeted, surgical changes - only modify what needs to be fixed
6. Do NOT add best practices that weren't in the missing practices list
7. Do NOT change base images unless there's a critical security issue
8. Do NOT add multi-stage builds unless explicitly needed for a critical issue
9. Do NOT add USER directives unless running as root is a CRITICAL security risk
10. Keep the same package versions and installation methods when possible
11. BE CONSERVATIVE: If the Dockerfile is already good ({overall_score}% overall), make MINIMAL changes
12. DO NOT make changes that could worsen the scores - only fix what's clearly broken

Your job is to apply the specific recommendations precisely, not to redesign the Dockerfile. If in doubt, make fewer changes rather than more."""
        
        kb_fix_guidance = ""
        if self.use_knowledge_base and self.knowledge_base:
            try:
                fix_patterns = self.knowledge_base.search_fix_patterns()
                if fix_patterns:
                    kb_fix_guidance = "\n\n=== KNOWLEDGE BASE FIX PATTERNS ===\n"
                    kb_fix_guidance += "Use these patterns when recommendations match:\n\n"
                    for pattern in fix_patterns[:10]:
                        kb_fix_guidance += f"[{pattern.severity.value.upper()}] {pattern.name}:\n"
                        kb_fix_guidance += f"  Description: {pattern.description}\n"
                        if pattern.template:
                            kb_fix_guidance += f"  Template: {pattern.template}\n"
                        elif pattern.replacement:
                            kb_fix_guidance += f"  Replacement: {pattern.replacement}\n"
                        if pattern.examples:
                            kb_fix_guidance += f"  Example: {pattern.examples[0]}\n"
                        kb_fix_guidance += "\n"
                    
                    lines = original_dockerfile.split('\n')
                    for line in lines:
                        if line.strip().upper().startswith('FROM'):
                            parts = line.split()
                            if len(parts) >= 2:
                                image_spec = parts[1]
                                image_name = image_spec.split(':')[0].split('@')[0]
                                recommended = self.knowledge_base.get_recommended_version(image_name)
                                if recommended:
                                    kb_fix_guidance += f"\nRecommended version for {image_name}: {recommended}\n"
            except Exception as e:
                print(f"  [WARNING] Failed to get knowledge base fix patterns: {e}")
        
        analysis_summary = f"""ANALYSIS RESULTS:

Security Score: {scores.get('security_score', 50)}/100
Efficiency Score: {scores.get('efficiency_score', 50)}/100
Best Practices Score: {scores.get('best_practices_score', 50)}/100
Overall Score: {scores.get('overall_score', 50)}/100
{kb_fix_guidance}
=== PRIMARY FIX GUIDE: SPECIFIC RECOMMENDATIONS ===
"""
        if recommendations:
            analysis_summary += f"\nYOU MUST FIX THESE {len(recommendations)} RECOMMENDATIONS:\n"
            for i, rec in enumerate(recommendations[:20], 1):  # Show more recommendations
                category = rec.get("category", "general")
                severity = rec.get("severity", "medium")
                message = rec.get("message", "")
                line = rec.get("instruction_line")
                line_str = f" (line {line})" if line else ""
                analysis_summary += f"{i}. [{severity.upper()}] {category}: {message}{line_str}\n"
            analysis_summary += "\nIMPORTANT: These recommendations contain the EXACT fixes needed. Apply each one precisely.\n"
        else:
            analysis_summary += "\nNo specific recommendations provided. Use the issue lists below as guidance.\n"
        
        analysis_summary += f"\n=== CONTEXT: ISSUE DESCRIPTIONS ===\n"
        analysis_summary += f"\nSECURITY RISKS ({len(security_risks)}):\n"
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
        
        user_prompt = f"""You must fix the Dockerfile by applying the SPECIFIC RECOMMENDATIONS listed above. Each recommendation tells you exactly what to change.

ORIGINAL DOCKERFILE:
```
{dockerfile_for_fixing}
```

{analysis_summary}

FIXING PROCESS:
1. Go through each SPECIFIC RECOMMENDATION in order
2. Find the corresponding line(s) in the Dockerfile
3. Apply the exact fix suggested by the recommendation
4. If a recommendation says to combine commands, combine them
5. If a recommendation says to separate commands, separate them
6. If a recommendation says to add something, add it
7. If a recommendation says to remove something, remove it

UNDERSTANDING COMMON FIXES:
- "Combine apt-get update and install in same RUN" → Put them in ONE RUN command
- "Separate apt-get update to allow caching" → Put update in its own RUN, then install in next RUN
- "Add --no-install-recommends" → Add this flag to apt-get install commands
- "Clean apt cache" → Add `apt-get clean && rm -rf /var/lib/apt/lists/*` after installs
- "Use specific version tag" → Change FROM image:latest to image:version
- "Add non-root user" → Add USER directive (only if explicitly recommended)

CRITICAL CONSTRAINTS:
- Apply ONLY the recommendations listed above - nothing more, nothing less
- DO NOT change base images unless a recommendation explicitly says to
- DO NOT add USER directives unless a recommendation explicitly says to
- DO NOT add multi-stage builds unless a recommendation explicitly says to
- DO NOT add HEALTHCHECK unless a recommendation explicitly says to
- DO NOT change package versions unless a recommendation explicitly says to
- PRESERVE all original functionality and behavior
- If a recommendation conflicts with another, prioritize security > performance > best practices

VERIFICATION:
After making changes, verify:
- Each recommendation has been addressed
- The Dockerfile still builds and works
- No new issues were introduced
- Original functionality is preserved

CRITICAL: Return ONLY the complete fixed Dockerfile. It MUST:
- Start with FROM (required - do not omit this!)
- Include ALL original instructions (FROM, SHELL, ENV, WORKDIR, VOLUME, etc.)
- Only modify the specific lines that need fixing
- Preserve all non-modified instructions exactly as they were
- Be a complete, valid Dockerfile

Return ONLY the raw Dockerfile starting with FROM. No explanations, no markdown, no code blocks."""
        
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
            has_from = any(line.strip().upper().startswith("FROM") for line in fixed_dockerfile.split('\n'))
            if not has_from:
                print(f"  [Error] Extracted Dockerfile missing FROM instruction")
                return {
                    "success": False,
                    "error": "Extracted Dockerfile is missing required FROM instruction",
                    "fixed_dockerfile": original_dockerfile,
                    "raw_response": response
                }
            
            syntax_errors = self._validate_dockerfile_syntax(fixed_dockerfile)
            if syntax_errors:
                print(f"  [Error] Dockerfile syntax errors detected: {', '.join(syntax_errors)}")
                return {
                    "success": False,
                    "error": f"Dockerfile syntax errors: {', '.join(syntax_errors)}",
                    "fixed_dockerfile": original_dockerfile,
                    "raw_response": response,
                    "syntax_errors": syntax_errors
                }
            
            original_lines = len(original_dockerfile.split('\n'))
            fixed_lines = len(fixed_dockerfile.split('\n'))
            print(f"  [Dockerfile Extracted] Original: {original_lines} lines, Fixed: {fixed_lines} lines")
            
            if fixed_dockerfile == original_dockerfile:
                print(f"  [Warning] Fixed Dockerfile is identical to original")
        else:
            print(f"  [Error] Failed to extract Dockerfile from LLM response")
            return {
                "success": False,
                "error": "Failed to extract Dockerfile from LLM response",
                "fixed_dockerfile": original_dockerfile,
                "raw_response": response
            }
        
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

    def _auto_fix_base_images(
        self,
        dockerfile_content: str
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Deterministically fix clearly bad/EOL base image tags using the knowledge base.

        Example:
        - golang:1.22-alpine3.9  →  golang:1.22-alpine
        - alpine:3.9             →  alpine:3.20

        Returns:
            (updated_dockerfile, list_of_changes)
        """
        if not self.knowledge_base:
            return dockerfile_content, []

        lines = dockerfile_content.split('\n')
        changes: List[Dict[str, str]] = []
        updated_lines: List[str] = []

        for line in lines:
            stripped = line.lstrip()
            if not stripped.upper().startswith('FROM'):
                updated_lines.append(line)
                continue

            parts = stripped.split()
            if len(parts) < 2:
                updated_lines.append(line)
                continue

            original_image_spec = parts[1]
            suggested = self.knowledge_base.suggest_fixed_image(original_image_spec)
            if not suggested or suggested == original_image_spec:
                updated_lines.append(line)
                continue

            leading_ws_len = len(line) - len(stripped)
            leading_ws = line[:leading_ws_len]

            rest = ""
            if len(parts) > 2:
                rest = " " + " ".join(parts[2:])

            new_stripped = f"FROM {suggested}{rest}"
            new_line = f"{leading_ws}{new_stripped}"
            updated_lines.append(new_line)

            reason = "knowledge base recommended replacement"
            changes.append(
                {
                    "original": original_image_spec,
                    "replacement": suggested,
                    "reason": reason,
                }
            )

        return "\n".join(updated_lines), changes
    
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
            code_content = cleaned[start+3:end].strip()
            if code_content.startswith("dockerfile") or code_content.startswith("docker"):
                code_content = code_content.split('\n', 1)[1] if '\n' in code_content else ""
            cleaned = cleaned[:start] + code_content + cleaned[end+3:]
            cleaned = cleaned.strip()
        
        cleaned = cleaned.replace("```", "").strip()
        
        lines = cleaned.split('\n')
        dockerfile_lines = []
        found_from = False
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                if found_from:
                    dockerfile_lines.append(line)
                continue
            
            if stripped.startswith('```') or '```' in stripped:
                continue
            
            if not found_from and not any(stripped.upper().startswith(kw) for kw in 
                ["FROM", "RUN", "COPY", "ADD", "WORKDIR", "ENV", "ARG", "VOLUME", 
                 "EXPOSE", "USER", "LABEL", "SHELL", "HEALTHCHECK", "ENTRYPOINT", "CMD", "STOPSIGNAL", "ONBUILD"]):
                continue
            
            if stripped.upper().startswith("FROM"):
                found_from = True
                dockerfile_lines.append(line)
            elif found_from:
                dockerfile_lines.append(line)
        
        result = '\n'.join(dockerfile_lines) if dockerfile_lines else cleaned
        
        result = result.replace('```', '').strip()
        
        if result and not any(line.strip().upper().startswith("FROM") for line in result.split('\n')):
            for line in cleaned.split('\n'):
                if line.strip().upper().startswith("FROM"):
                    result = line + '\n' + result
                    break
        
        return result
    
    def _validate_dockerfile_syntax(self, dockerfile_content: str) -> List[str]:
        """Validate Dockerfile syntax and return list of errors"""
        errors = []
        lines = dockerfile_content.split('\n')
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if not stripped or stripped.startswith('#'):
                continue
            
            if stripped.upper().startswith('RUN'):
                if stripped.endswith('&') and not stripped.endswith('&&'):
                    errors.append(f"Line {i}: RUN command ends with incomplete '&' (should be '&&' or complete command)")
                if stripped.endswith('&&') and i == len(lines):
                    errors.append(f"Line {i}: RUN command ends with '&&' but has no continuation")
                if stripped.endswith('\\'):
                    if i < len(lines):
                        next_line = lines[i].strip()
                        if not next_line or next_line.startswith('#'):
                            errors.append(f"Line {i}: Line continuation '\\' but next line is empty or comment")
            
            if stripped.upper().startswith(('ENV', 'ARG')):
                tokens = stripped.split()
                if len(tokens) == 1:
                    errors.append(f"Line {i}: ENV/ARG command missing variable name")
        
        return errors





