import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .knowledge_base import KnowledgeBase, BaseImageInfo, FixPattern, BestPractice, Severity, Category
from .kb_initializer import initialize_knowledge_base


def cmd_init(args):
    kb = KnowledgeBase()
    initialize_knowledge_base(kb)
    print("✓ Knowledge base initialized successfully!")
    print(f"  - Base images: {len(kb.base_images)}")
    print(f"  - Fix patterns: {len(kb.fix_patterns)}")
    print(f"  - Best practices: {len(kb.best_practices)}")
    print(f"  - Security advisories: {len(kb.security_advisories)}")


def cmd_list(args):
    kb = KnowledgeBase()
    
    if args.type == "base-images" or args.type == "all":
        print("\n=== BASE IMAGES ===")
        for name, info in kb.base_images.items():
            print(f"\n{name}:")
            print(f"  Recommended: {info.recommended}")
            print(f"  Latest: {info.latest_stable}")
            if info.eol_versions:
                print(f"  EOL: {', '.join(info.eol_versions)}")
    
    if args.type == "fix-patterns" or args.type == "all":
        print("\n=== FIX PATTERNS ===")
        for pattern_id, pattern in kb.fix_patterns.items():
            print(f"\n[{pattern.severity.value.upper()}] {pattern.name} ({pattern_id}):")
            print(f"  {pattern.description}")
            if pattern.template:
                print(f"  Template: {pattern.template[:100]}...")
    
    if args.type == "best-practices" or args.type == "all":
        print("\n=== BEST PRACTICES ===")
        for practice_id, practice in kb.best_practices.items():
            print(f"\n[{practice.priority}/10] {practice.name} ({practice_id}):")
            print(f"  {practice.description}")
    
    if args.type == "advisories" or args.type == "all":
        print("\n=== SECURITY ADVISORIES ===")
        for advisory_id, advisory in kb.security_advisories.items():
            print(f"\n[{advisory.severity.value.upper()}] {advisory_id}:")
            print(f"  {advisory.description}")
            if advisory.fixed_version:
                print(f"  Fixed in: {advisory.fixed_version}")


def cmd_query(args):
    kb = KnowledgeBase()
    
    if args.query_type == "base-image":
        info = kb.get_base_image_info(args.value)
        if info:
            print(f"\nBase Image: {info.name}")
            print(f"  Recommended: {info.recommended}")
            print(f"  Latest: {info.latest_stable}")
            if info.eol_versions:
                print(f"  EOL versions: {', '.join(info.eol_versions)}")
            if info.security_issues:
                print(f"  Security issues: {len(info.security_issues)}")
        else:
            print(f"No information found for: {args.value}")
    
    elif args.query_type == "fix-pattern":
        pattern = kb.get_fix_pattern(args.value)
        if pattern:
            print(f"\nFix Pattern: {pattern.name}")
            print(f"  Category: {pattern.category.value}")
            print(f"  Severity: {pattern.severity.value}")
            print(f"  Description: {pattern.description}")
            if pattern.template:
                print(f"  Template:\n{pattern.template}")
            if pattern.examples:
                print(f"  Examples: {pattern.examples}")
        else:
            print(f"No fix pattern found: {args.value}")
    
    elif args.query_type == "recommended-version":
        version = kb.get_recommended_version(args.value)
        if version:
            print(f"Recommended version for {args.value}: {version}")
        else:
            print(f"No recommended version found for: {args.value}")


def cmd_add(args):
    kb = KnowledgeBase()
    
    if args.type == "base-image":
        data = json.loads(args.data)
        info = BaseImageInfo(**data)
        kb.base_images[info.name] = info
        kb.save()
        print(f"✓ Added base image: {info.name}")
    
    elif args.type == "fix-pattern":
        data = json.loads(args.data)
        data['category'] = Category(data['category'])
        data['severity'] = Severity(data['severity'])
        pattern = FixPattern(**data)
        kb.fix_patterns[pattern.id] = pattern
        kb.save()
        print(f"✓ Added fix pattern: {pattern.name}")
    
    elif args.type == "best-practice":
        data = json.loads(args.data)
        data['category'] = Category(data['category'])
        practice = BestPractice(**data)
        kb.best_practices[practice.id] = practice
        kb.save()
        print(f"✓ Added best practice: {practice.name}")


def cmd_stats(args):
    kb = KnowledgeBase()
    
    print("\n=== KNOWLEDGE BASE STATISTICS ===")
    print(f"\nBase Images: {len(kb.base_images)}")
    print(f"Fix Patterns: {len(kb.fix_patterns)}")
    print(f"Best Practices: {len(kb.best_practices)}")
    print(f"Historical Fixes: {len(kb.historical_fixes)}")
    print(f"Security Advisories: {len(kb.security_advisories)}")
    
    severity_counts = {}
    for pattern in kb.fix_patterns.values():
        sev = pattern.severity.value
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    if severity_counts:
        print("\nFix Pattern Severity Breakdown:")
        for sev, count in sorted(severity_counts.items(), reverse=True):
            print(f"  {sev.upper()}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Management Tool")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    init_parser = subparsers.add_parser('init', help='Initialize knowledge base')
    init_parser.set_defaults(func=cmd_init)
    
    list_parser = subparsers.add_parser('list', help='List knowledge base entries')
    list_parser.add_argument('--type', choices=['all', 'base-images', 'fix-patterns', 'best-practices', 'advisories'],
                           default='all', help='Type of entries to list')
    list_parser.set_defaults(func=cmd_list)
    
    query_parser = subparsers.add_parser('query', help='Query knowledge base')
    query_parser.add_argument('query_type', choices=['base-image', 'fix-pattern', 'recommended-version'],
                             help='Type of query')
    query_parser.add_argument('value', help='Value to query')
    query_parser.set_defaults(func=cmd_query)
    
    add_parser = subparsers.add_parser('add', help='Add entry to knowledge base')
    add_parser.add_argument('type', choices=['base-image', 'fix-pattern', 'best-practice'],
                          help='Type of entry to add')
    add_parser.add_argument('--data', required=True, help='JSON data for the entry')
    add_parser.set_defaults(func=cmd_add)
    
    stats_parser = subparsers.add_parser('stats', help='Show knowledge base statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

