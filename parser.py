import re
from typing import List, Dict
import sys


def parse_dockerfile(contents: str) -> List[Dict[str, str]]:
    instructions: List[Dict[str, str]] = []
    current = ""
    for line in contents.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if stripped.lower().startswith("# syntax="):
                instructions.append({"instruction": "SYNTAX", "value": stripped})
            continue=
        def remove_inline_comment(s: str) -> str:
            in_quote = False
            result = []
            for char in s:
                if char in ('"', "'"):
                    in_quote = not in_quote
                if char == '#' and not in_quote:
                    break
                result.append(char)
            return ''.join(result).rstrip()

        stripped = remove_inline_comment(stripped)
        if not stripped:
            continue
        if stripped.endswith("\\"):
            current += stripped[:-1].rstrip() + " "
            continue
        current += stripped
        parts = current.split(None, 1)
        if not parts:
            current = ""
            continue
        instr = parts[0].upper()
        value = parts[1] if len(parts) > 1 else ""
        instructions.append({"instruction": instr, "value": value})
        current = ""
    return instructions


def analyse_instructions(instructions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    recs: List[Dict[str, str]] = []
    base_image = None
    user_specified = False
    run_lines = []
    for idx, item in enumerate(instructions):
        instr = item["instruction"]
        value = item["value"]
        if instr == "FROM":
            base_image = value
            if ":" not in value or value.strip().endswith(":latest"):
                recs.append({
                    "severity": "warning",
                    "instruction_index": idx,
                    "message": "Specify a fixed version tag or digest for the base image for reproducibility and security."
                })
        elif instr == "RUN":
            run_lines.append((idx, value))
            if "apt-get" in value or "apt " in value:
                if "--no-install-recommends" not in value:
                    recs.append({
                        "severity": "info",
                        "instruction_index": idx,
                        "message": "Use --no-install-recommends with apt-get to avoid unnecessary packages."
                    })
                if not re.search(r"apt-get\s+clean", value) and not re.search(r"rm\s+-rf\s+/var/lib/apt/lists", value):
                    recs.append({
                        "severity": "info",
                        "instruction_index": idx,
                        "message": "Clean apt caches (e.g., apt-get clean && rm -rf /var/lib/apt/lists/*) to reduce image size."
                    })
            if "&&" not in value:
                recs.append({
                    "severity": "info",
                    "instruction_index": idx,
                    "message": "Combine multiple shell commands with '&&' in a single RUN to reduce layers."
                })
        elif instr == "ADD":
            if not re.search(r"\.tar(\.gz|\.bz2|\.xz)?", value):
                recs.append({
                    "severity": "info",
                    "instruction_index": idx,
                    "message": "Use COPY instead of ADD when not extracting archives to improve caching behaviour."
                })
        elif instr == "USER":
            user_specified = True
    if len(run_lines) > 3:
        combined = " && ".join(cmd for _, cmd in run_lines)
        if "apt-get" in combined:
            recs.append({
                "severity": "suggestion",
                "instruction_index": -1,
                "message": "Consider using multi-stage builds to separate build-time dependencies from the final runtime image."
            })
    if not user_specified:
        recs.append({
            "severity": "warning",
            "instruction_index": -1,
            "message": "No USER directive found. Running as root can be risky; consider adding a non-root user."
        })
    return recs


def analyse_dockerfile(path: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            contents = f.read()
    except FileNotFoundError:
        print(f"Error: Dockerfile not found: {path}")
        return
    instructions = parse_dockerfile(contents)
    recs = analyse_instructions(instructions)
    for rec in recs:
        idx = rec["instruction_index"]
        loc = f"instruction {idx}" if idx >= 0 else "(general)"
        print(f"{rec['severity'].upper()}: {loc} – {rec['message']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python docker_ast_parser.py <path_to_Dockerfile>")
        sys.exit(1)
    analyse_dockerfile(sys.argv[1])