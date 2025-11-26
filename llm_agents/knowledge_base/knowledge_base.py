"""
Dockerfile Optimization Knowledge Base

A comprehensive knowledge base system for Dockerfile optimization that provides:
- Base image version information
- Fix patterns and templates
- Common best practices
- Historical fix patterns
- Security advisories
- Version compatibility matrices
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    BEST_PRACTICE = "best_practice"
    OPTIMIZATION = "optimization"
    COMPATIBILITY = "compatibility"


@dataclass
class BaseImageInfo:
    """Information about a base image"""
    name: str
    latest_stable: str
    recommended: str
    eol_versions: List[str]
    security_issues: Dict[str, str]  # version -> description
    release_date: Optional[str] = None
    eol_date: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class FixPattern:
    """A pattern for fixing common Dockerfile issues"""
    id: str
    name: str
    category: Category
    severity: Severity
    description: str
    pattern: str  # Regex or string pattern to match
    replacement: str  # Replacement template
    template: Optional[str] = None  # Full template if complex
    conditions: Optional[Dict[str, Any]] = None  # When to apply
    examples: Optional[List[str]] = None


@dataclass
class BestPractice:
    """A Dockerfile best practice"""
    id: str
    name: str
    category: Category
    description: str
    implementation: str  # How to implement
    example: Optional[str] = None
    priority: int = 5  # 1-10, higher = more important


@dataclass
class HistoricalFix:
    """A historical fix that was successful"""
    id: str
    original_pattern: str
    fixed_pattern: str
    issue_type: str
    success_rate: float  # 0.0-1.0
    usage_count: int
    last_used: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class SecurityAdvisory:
    """Security advisory for base images or packages"""
    id: str
    base_image: Optional[str]
    package: Optional[str]
    cve: Optional[str]
    severity: Severity
    description: str
    affected_versions: List[str]
    fixed_version: Optional[str] = None
    published_date: Optional[str] = None


class KnowledgeBase:
    
    def __init__(self, kb_dir: Optional[str] = None):
        if kb_dir is None:
            kb_dir = Path(__file__).parent / "knowledge_base"
        
        self.kb_dir = Path(kb_dir)
        self.kb_dir.mkdir(exist_ok=True)
        
        self.base_images: Dict[str, BaseImageInfo] = {}
        self.fix_patterns: Dict[str, FixPattern] = {}
        self.best_practices: Dict[str, BestPractice] = {}
        self.historical_fixes: Dict[str, HistoricalFix] = {}
        self.security_advisories: Dict[str, SecurityAdvisory] = {}
        
        self.load()
    
    def load(self):
        base_images_file = self.kb_dir / "base_images.json"
        if base_images_file.exists():
            with open(base_images_file, 'r') as f:
                data = json.load(f)
                for name, info in data.items():
                    self.base_images[name] = BaseImageInfo(**info)
        
        fix_patterns_file = self.kb_dir / "fix_patterns.json"
        if fix_patterns_file.exists():
            with open(fix_patterns_file, 'r') as f:
                data = json.load(f)
                for pattern_id, pattern_data in data.items():
                    # Handle enum values that might be stored as "Category.SECURITY" or just "SECURITY"
                    category_val = pattern_data['category']
                    if isinstance(category_val, str):
                        if category_val.startswith('Category.'):
                            category_val = category_val.replace('Category.', '').lower()
                        elif category_val.isupper():
                            category_val = category_val.lower()
                    pattern_data['category'] = Category(category_val)
                    
                    severity_val = pattern_data['severity']
                    if isinstance(severity_val, str):
                        if severity_val.startswith('Severity.'):
                            severity_val = severity_val.replace('Severity.', '').lower()
                        elif severity_val.isupper():
                            severity_val = severity_val.lower()
                    pattern_data['severity'] = Severity(severity_val)
                    self.fix_patterns[pattern_id] = FixPattern(**pattern_data)
        
        best_practices_file = self.kb_dir / "best_practices.json"
        if best_practices_file.exists():
            with open(best_practices_file, 'r') as f:
                data = json.load(f)
                for practice_id, practice_data in data.items():
                    # Handle enum values that might be stored as "Category.SECURITY" or just "SECURITY"
                    category_val = practice_data['category']
                    if isinstance(category_val, str):
                        if category_val.startswith('Category.'):
                            category_val = category_val.replace('Category.', '').lower()
                        elif category_val.isupper():
                            category_val = category_val.lower()
                    practice_data['category'] = Category(category_val)
                    self.best_practices[practice_id] = BestPractice(**practice_data)
        
        historical_fixes_file = self.kb_dir / "historical_fixes.json"
        if historical_fixes_file.exists():
            with open(historical_fixes_file, 'r') as f:
                data = json.load(f)
                for fix_id, fix_data in data.items():
                    self.historical_fixes[fix_id] = HistoricalFix(**fix_data)
        
        security_advisories_file = self.kb_dir / "security_advisories.json"
        if security_advisories_file.exists():
            with open(security_advisories_file, 'r') as f:
                data = json.load(f)
                for advisory_id, advisory_data in data.items():
                    # Handle enum values that might be stored as "Severity.CRITICAL" or just "CRITICAL"
                    severity_val = advisory_data['severity']
                    if isinstance(severity_val, str):
                        if severity_val.startswith('Severity.'):
                            severity_val = severity_val.replace('Severity.', '').lower()
                        elif severity_val.isupper():
                            severity_val = severity_val.lower()
                    advisory_data['severity'] = Severity(severity_val)
                    self.security_advisories[advisory_id] = SecurityAdvisory(**advisory_data)
    
    def save(self):
        base_images_file = self.kb_dir / "base_images.json"
        with open(base_images_file, 'w') as f:
            data = {
                name: asdict(info) 
                for name, info in self.base_images.items()
            }
            json.dump(data, f, indent=2)
        
        fix_patterns_file = self.kb_dir / "fix_patterns.json"
        with open(fix_patterns_file, 'w') as f:
            data = {}
            for pattern_id, pattern in self.fix_patterns.items():
                pattern_dict = asdict(pattern)
                # Convert enum to just the value (not "Category.SECURITY" but "SECURITY")
                pattern_dict['category'] = pattern.category.value
                pattern_dict['severity'] = pattern.severity.value
                data[pattern_id] = pattern_dict
            json.dump(data, f, indent=2, default=str)
        
        best_practices_file = self.kb_dir / "best_practices.json"
        with open(best_practices_file, 'w') as f:
            data = {}
            for practice_id, practice in self.best_practices.items():
                practice_dict = asdict(practice)
                # Convert enum to just the value (not "Category.SECURITY" but "SECURITY")
                practice_dict['category'] = practice.category.value
                data[practice_id] = practice_dict
            json.dump(data, f, indent=2, default=str)
        
        historical_fixes_file = self.kb_dir / "historical_fixes.json"
        with open(historical_fixes_file, 'w') as f:
            data = {
                fix_id: asdict(fix) 
                for fix_id, fix in self.historical_fixes.items()
            }
            json.dump(data, f, indent=2, default=str)
        
        security_advisories_file = self.kb_dir / "security_advisories.json"
        with open(security_advisories_file, 'w') as f:
            data = {}
            for advisory_id, advisory in self.security_advisories.items():
                advisory_dict = asdict(advisory)
                # Convert enum to just the value (not "Severity.CRITICAL" but "CRITICAL")
                advisory_dict['severity'] = advisory.severity.value
                data[advisory_id] = advisory_dict
            json.dump(data, f, indent=2, default=str)
    
    def get_base_image_info(self, image_name: str) -> Optional[BaseImageInfo]:
        if image_name in self.base_images:
            return self.base_images[image_name]
        
        for name, info in self.base_images.items():
            if image_name.startswith(name) or name in image_name:
                return info
        
        return None
    
    def get_recommended_version(self, image_name: str) -> Optional[str]:
        info = self.get_base_image_info(image_name)
        if info:
            return info.recommended
        return None

    def analyze_image_spec(self, image_spec: str) -> Dict[str, Any]:
        """Analyze a Docker image spec (e.g., 'golang:1.22-alpine3.9') using the KB.

        Returns a dict with:
        - image_spec: original spec
        - image_name: base image name (e.g., 'golang')
        - tag: tag portion if present
        - issues: list of issue identifiers
        - is_eol: whether the tag directly matches an EOL version for that image
        - is_golang_alpine_eol_combo: whether this is a Go+Alpine combo using an EOL Alpine
        - alpine_version: parsed Alpine version (for Go+Alpine combos)
        - recommended: recommended tag for this base image (if known)
        - base_info: serialized BaseImageInfo (if known)
        """
        result: Dict[str, Any] = {
            "image_spec": image_spec,
            "issues": []
        }

        # Strip any digest first (e.g., image:tag@sha256:...)
        name_and_tag = image_spec.split('@', 1)[0]
        if ':' in name_and_tag:
            image_name, tag = name_and_tag.split(':', 1)
        else:
            image_name, tag = name_and_tag, None

        image_name = image_name.strip()
        if not image_name:
            return result

        result["image_name"] = image_name
        result["tag"] = tag

        info = self.get_base_image_info(image_name)
        if info:
            result["base_info"] = asdict(info)
            if tag and tag in info.eol_versions:
                result["is_eol"] = True
                result["issues"].append("eol_version")
            else:
                result["is_eol"] = False
            result["recommended"] = info.recommended
        else:
            result["is_eol"] = False

        # Special handling for Go + Alpine combos like golang:1.22-alpine3.9
        is_golang_alpine_eol_combo = False
        alpine_version: Optional[str] = None
        if image_name.startswith("golang") and tag and "alpine" in tag:
            alpine_idx = tag.find("alpine")
            suffix = tag[alpine_idx + len("alpine") :]
            # Accept formats like "3.9" or "-3.9"
            alpine_version = suffix.lstrip('-') if suffix else None
            if alpine_version:
                alpine_info = self.get_base_image_info("alpine")
                if alpine_info and alpine_version in alpine_info.eol_versions:
                    is_golang_alpine_eol_combo = True
                    result["issues"].append("golang_alpine_eol_combo")

        result["is_golang_alpine_eol_combo"] = is_golang_alpine_eol_combo
        if alpine_version:
            result["alpine_version"] = alpine_version

        return result

    def suggest_fixed_image(self, image_spec: str) -> Optional[str]:
        """Suggest a safer/recommended replacement for a problematic image spec.

        Uses simple, deterministic rules based on the knowledge base:
        - For Go+Alpine combos using an EOL Alpine (e.g., golang:1.22-alpine3.9),
          prefer the recommended Go tag from the KB (e.g., golang:1.22-alpine).
        - For direct EOL tags (e.g., alpine:3.9), prefer the KB's recommended tag
          for that base image.
        """
        analysis = self.analyze_image_spec(image_spec)
        issues = analysis.get("issues") or []

        # If this is an EOL Go+Alpine combo, prefer the recommended Go image
        if "golang_alpine_eol_combo" in issues:
            golang_info = self.get_base_image_info("golang")
            if golang_info and golang_info.recommended:
                return golang_info.recommended

        # For any direct EOL tag, suggest the recommended tag for that base image
        if "eol_version" in issues:
            recommended = analysis.get("recommended")
            if recommended:
                return recommended

        return None
    
    def is_eol_version(self, image_name: str, version: str) -> bool:
        info = self.get_base_image_info(image_name)
        if info:
            return version in info.eol_versions
        return False
    
    def search_fix_patterns(
        self, 
        category: Optional[Category] = None,
        severity: Optional[Severity] = None,
        search_term: Optional[str] = None
    ) -> List[FixPattern]:
        results = list(self.fix_patterns.values())
        
        if category:
            results = [p for p in results if p.category == category]
        
        if severity:
            results = [p for p in results if p.severity == severity]
        
        if search_term:
            search_term_lower = search_term.lower()
            results = [
                p for p in results 
                if search_term_lower in p.name.lower() 
                or search_term_lower in p.description.lower()
            ]
        
        return results
    
    def get_fix_pattern(self, pattern_id: str) -> Optional[FixPattern]:
        return self.fix_patterns.get(pattern_id)
    
    def get_best_practices(
        self,
        category: Optional[Category] = None,
        min_priority: int = 0
    ) -> List[BestPractice]:
        results = list(self.best_practices.values())
        
        if category:
            results = [p for p in results if p.category == category]
        
        results = [p for p in results if p.priority >= min_priority]
        
        return sorted(results, key=lambda x: x.priority, reverse=True)
    
    def find_similar_historical_fix(self, original_pattern: str) -> Optional[HistoricalFix]:
        for fix in self.historical_fixes.values():
            if original_pattern in fix.original_pattern or fix.original_pattern in original_pattern:
                return fix
        return None
    
    def record_fix(
        self,
        original_pattern: str,
        fixed_pattern: str,
        issue_type: str,
        success: bool = True
    ):
        fix_id = f"{issue_type}_{hash(original_pattern) % 10000}"
        
        if fix_id in self.historical_fixes:
            fix = self.historical_fixes[fix_id]
            fix.usage_count += 1
            if success:
                fix.success_rate = (fix.success_rate * (fix.usage_count - 1) + 1.0) / fix.usage_count
            else:
                fix.success_rate = (fix.success_rate * (fix.usage_count - 1) + 0.0) / fix.usage_count
            fix.last_used = datetime.now().isoformat()
        else:
            fix = HistoricalFix(
                id=fix_id,
                original_pattern=original_pattern,
                fixed_pattern=fixed_pattern,
                issue_type=issue_type,
                success_rate=1.0 if success else 0.0,
                usage_count=1,
                last_used=datetime.now().isoformat()
            )
            self.historical_fixes[fix_id] = fix
        
        self.save()
    
    def get_security_advisories(
        self,
        base_image: Optional[str] = None,
        severity: Optional[Severity] = None
    ) -> List[SecurityAdvisory]:
        results = list(self.security_advisories.values())
        
        if base_image:
            results = [a for a in results if a.base_image == base_image]
        
        if severity:
            results = [a for a in results if a.severity == severity]
        
        return sorted(results, key=lambda x: x.severity.value, reverse=True)
    
    def get_context_for_analysis(self, dockerfile_content: str) -> Dict[str, Any]:
        context = {
            "base_images": {},
            "fix_patterns": [],
            "best_practices": [],
            "security_advisories": [],
            "historical_fixes": []
        }
        
        lines = dockerfile_content.split('\n')
        for line in lines:
            if line.strip().upper().startswith('FROM'):
                parts = line.split()
                if len(parts) >= 2:
                    image_spec = parts[1]
                    image_name = image_spec.split(':')[0].split('@')[0]
                    info = self.get_base_image_info(image_name)
                    if info:
                        context["base_images"][image_name] = asdict(info)
        
        context["fix_patterns"] = [
            asdict(p) for p in self.search_fix_patterns()
        ]
        
        context["best_practices"] = [
            asdict(p) for p in self.get_best_practices(min_priority=7)
        ]
        
        for image_name in context["base_images"].keys():
            advisories = self.get_security_advisories(base_image=image_name)
            context["security_advisories"].extend([asdict(a) for a in advisories])
        
        return context

