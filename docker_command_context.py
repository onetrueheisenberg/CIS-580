"""Utilities for extracting Docker command context from strace logs.

This script scans a log file (such as an strace capture) for lines that
contain Docker-related command executions and prints a table with the
surrounding context lines.  Each matched command is reported with the ten
lines before and after the match (configurable) so that the Docker invocation
can be inspected in-place with relevant system call activity.

Example
-------
    python docker_command_context.py strace_docker_build.log --radius 10

The output groups each detected command and renders a small ASCII table that
shows line numbers, an indicator for the command line itself, and the content
of the surrounding lines.
"""

from __future__ import annotations

import argparse
import pathlib
from typing import Iterable, List, Sequence, Tuple

CONTEXT_RADIUS_DEFAULT = 10
DEFAULT_KEYWORDS = ("docker", "dockerd", "containerd", "buildkit")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Extract Docker command context from a log file",
    )
    parser.add_argument(
        "log_path",
        type=pathlib.Path,
        help="Path to the log file (e.g. strace_docker_build.log)",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=CONTEXT_RADIUS_DEFAULT,
        help=(
            "Number of context lines to include before and after the matched "
            "command (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=list(DEFAULT_KEYWORDS),
        help=(
            "Keywords that mark a line as Docker-related. Matching is case-"
            "insensitive. Defaults to %(default)s"
        ),
    )
    return parser.parse_args(argv)


def read_lines(path: pathlib.Path) -> List[str]:
    """Read the log file, returning a list of lines."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError as exc:
        raise SystemExit(f"Log file not found: {path}") from exc


def find_matches(lines: Sequence[str], keywords: Iterable[str]) -> List[int]:
    """Return indices of lines containing the provided keywords."""
    lowered_keywords = [kw.lower() for kw in keywords]
    matches: List[int] = []
    for idx, line in enumerate(lines):
        text = line.lower()
        if any(kw in text for kw in lowered_keywords):
            matches.append(idx)
    return matches


def build_context(
    lines: Sequence[str],
    match_index: int,
    radius: int,
) -> List[Tuple[int, str, str]]:
    """Build the context table for a particular match.

    Returns a list of tuples ``(line_number, marker, content)`` where ``marker``
    is ``"*"`` for the matched command line and blank otherwise.
    """
    start = max(0, match_index - radius)
    end = min(len(lines), match_index + radius + 1)
    context_rows: List[Tuple[int, str, str]] = []
    for idx in range(start, end):
        marker = "*" if idx == match_index else ""
        context_rows.append((idx + 1, marker, lines[idx]))
    return context_rows


def format_table(rows: Sequence[Tuple[int, str, str]]) -> str:
    """Format context rows into an ASCII table."""
    if not rows:
        return ""

    line_width = max(len(str(row[0])) for row in rows)
    marker_width = 1
    content_width = max(len(row[2]) for row in rows)

    def make_border(char: str = "-") -> str:
        return "+" + char * (line_width + 2) + "+" + char * (marker_width + 2) + "+" + char * (content_width + 2) + "+"

    header = (
        f"| {'Line'.ljust(line_width)} | {'*'.center(marker_width)} | {'Content'.ljust(content_width)} |"
    )

    lines_out = [make_border("="), header, make_border("-")]
    for line_no, marker, content in rows:
        lines_out.append(
            "| "
            f"{str(line_no).rjust(line_width)}"
            " | "
            f"{marker.center(marker_width)}"
            " | "
            f"{content.ljust(content_width)}"
            " |"
        )
    lines_out.append(make_border("="))
    return "\n".join(lines_out)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    lines = read_lines(args.log_path)
    matches = find_matches(lines, args.keywords)

    if not matches:
        print(
            "No Docker-related commands found. Try adjusting the keyword list "
            "or verifying the log file."
        )
        return 0

    for match_number, match_index in enumerate(matches, start=1):
        print(f"Match {match_number}: line {match_index + 1}")
        context_rows = build_context(lines, match_index, args.radius)
        print(format_table(context_rows))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
