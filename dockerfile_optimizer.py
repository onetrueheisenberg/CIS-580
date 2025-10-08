import csv
import os
import re
import subprocess
import sys
from typing import Dict, List


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
            continue
        def remove_inline_comment(s: str) -> str:
            in_quote = False
            result: List[str] = []
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
    user_specified = False
    run_lines: List[tuple[int, str]] = []
    for idx, item in enumerate(instructions):
        instr = item["instruction"]
        value = item["value"]
        if instr == "FROM":
            if ":" not in value or value.strip().endswith(":latest"):
                recs.append({
                    "severity": "warning",
                    "instruction_index": idx,
                    "message": "Specify a fixed version tag or digest for the base image for reproducibility and security.",
                })
        elif instr == "RUN":
            run_lines.append((idx, value))
            if "apt-get" in value or "apt " in value:
                if "--no-install-recommends" not in value:
                    recs.append({
                        "severity": "info",
                        "instruction_index": idx,
                        "message": "Use --no-install-recommends with apt-get to avoid unnecessary packages.",
                    })
                if not re.search(r"apt-get\s+clean", value) and not re.search(r"rm\s+-rf\s+/var/lib/apt/lists", value):
                    recs.append({
                        "severity": "info",
                        "instruction_index": idx,
                        "message": "Clean apt caches (e.g., apt-get clean && rm -rf /var/lib/apt/lists/*) to reduce image size.",
                    })
                if "apt-get update" in value and "apt-get install" not in value:
                    recs.append({
                        "severity": "info",
                        "instruction_index": idx,
                        "message": "Run apt-get update and install in the same RUN layer to improve caching and size.",
                    })
            if "pip install" in value and "--no-cache-dir" not in value:
                recs.append({
                    "severity": "info",
                    "instruction_index": idx,
                    "message": "Use --no-cache-dir with pip install to reduce image size.",
                })
            if re.search(r"(curl|wget).*\|.*(sh|bash)", value):
                recs.append({
                    "severity": "warning",
                    "instruction_index": idx,
                    "message": "Avoid piping curl/wget directly to shell; download and verify scripts before execution.",
                })
            if "&&" not in value:
                recs.append({
                    "severity": "info",
                    "instruction_index": idx,
                    "message": "Combine multiple shell commands with '&&' in a single RUN to reduce layers.",
                })
        elif instr == "ADD":
            if not re.search(r"\.tar(\.gz|\.bz2|\.xz)?", value):
                recs.append({
                    "severity": "info",
                    "instruction_index": idx,
                    "message": "Use COPY instead of ADD when not extracting archives to improve caching behaviour.",
                })
        elif instr == "USER":
            user_specified = True
    if len(run_lines) > 3:
        combined = " && ".join(cmd for _, cmd in run_lines)
        if "apt-get" in combined:
            recs.append({
                "severity": "suggestion",
                "instruction_index": -1,
                "message": "Consider using multi-stage builds to separate build-time dependencies from the final runtime image.",
            })
    if not user_specified:
        recs.append({
            "severity": "warning",
            "instruction_index": -1,
            "message": "No USER directive found. Running as root can be risky; consider adding a non-root user.",
        })
    if not any(item["instruction"] == "HEALTHCHECK" for item in instructions):
        recs.append({
            "severity": "suggestion",
            "instruction_index": -1,
            "message": "Consider adding a HEALTHCHECK instruction for improved reliability.",
        })
    return recs


def analyse_dockerfile(path: str) -> List[Dict[str, str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            contents = f.read()
    except FileNotFoundError:
        return [{"severity": "error", "instruction_index": -1, "message": f"Dockerfile not found: {path}"}]
    instructions = parse_dockerfile(contents)
    return analyse_instructions(instructions)


def find_dockerfiles(repo_path: str) -> List[str]:
    matches: List[str] = []
    for root, _dirs, files in os.walk(repo_path):
        for name in files:
            lname = name.lower()
            if lname == "dockerfile" or lname.startswith("dockerfile."):
                matches.append(os.path.join(root, name))
    return matches


def clone_repo(url: str, base_dir: str) -> str:
    repo_name = url.rstrip("/").split("/")[-1]
    dest = os.path.join(base_dir, repo_name)
    if not os.path.exists(dest):
        subprocess.run(["git", "clone", "--depth", "1", url, dest], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def process_csv(csv_path: str, limit: int | None = None) -> None:
    repos_dir = "cloned_repos"
    os.makedirs(repos_dir, exist_ok=True)
    processed = 0
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            repo_url = row.get("Repository") or row.get("Repo")
            if not repo_url:
                continue
            repo_path = clone_repo(repo_url, repos_dir)
            for dockerfile in find_dockerfiles(repo_path):
                print(f"Analyzing {dockerfile}")
                recs = analyse_dockerfile(dockerfile)
                for rec in recs:
                    idx = rec["instruction_index"]
                    loc = f"instruction {idx}" if idx >= 0 else "(general)"
                    print(f"  {rec['severity'].upper()}: {loc} – {rec['message']}")
            processed += 1
            if limit is not None and processed >= limit:
                break


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Analyze Dockerfiles from repositories listed in a CSV file.")
    parser.add_argument("--csv", dest="csv_path", help="Path to CSV file containing repository URLs")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of repositories to process")
    parser.add_argument("--repo-path", help="Analyze a single local repository instead of CSV", default=None)
    args = parser.parse_args()
    if args.repo_path:
        for dockerfile in find_dockerfiles(args.repo_path):
            print(f"Analyzing {dockerfile}")
            recs = analyse_dockerfile(dockerfile)
            for rec in recs:
                idx = rec["instruction_index"]
                loc = f"instruction {idx}" if idx >= 0 else "(general)"
                print(f"  {rec['severity'].upper()}: {loc} – {rec['message']}")
    elif args.csv_path:
        process_csv(args.csv_path, limit=args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
