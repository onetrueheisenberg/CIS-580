"""Runtime analyzer for Docker images and containers.

This module inspects images that are currently available on the host and
provides actionable recommendations that focus on image size, security, and
runtime performance. The same heuristics are also applied to running containers
to surface configuration issues such as missing health checks or security
hardening gaps.

The script depends on the Docker CLI. When Docker is unavailable or the user
lacks sufficient permissions, a human-friendly error message is displayed
instead of raising raw subprocess exceptions.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass
class Recommendation:
    """Represents an optimization opportunity for an image or container."""

    subject: str
    severity: str
    message: str


class DockerUnavailableError(RuntimeError):
    """Raised when Docker cannot be invoked."""


def _ensure_docker_available() -> None:
    if shutil.which("docker") is None:
        raise DockerUnavailableError(
            "Docker CLI not found in PATH. Install Docker or ensure it is accessible."
        )


def _run_docker_command(args: List[str]) -> str:
    _ensure_docker_available()
    try:
        result = subprocess.run(
            ["docker", *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise DockerUnavailableError("Docker CLI could not be executed") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Docker command failed: docker {' '.join(args)}\n{exc.stderr.strip()}"
        ) from exc
    return result.stdout


def _parse_json_lines(output: str) -> Iterable[Dict[str, object]]:
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def list_images() -> List[Dict[str, object]]:
    output = _run_docker_command([
        "images",
        "--digests",
        "--format",
        "{{json .}}",
    ])
    return list(_parse_json_lines(output))


def inspect_image(image_id: str) -> Dict[str, object]:
    output = _run_docker_command(["inspect", image_id])
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Failed to parse docker inspect output for {image_id}") from exc
    if not data:
        raise RuntimeError(f"docker inspect returned no data for image {image_id}")
    return data[0]


def image_history(image_id: str) -> List[Dict[str, object]]:
    output = _run_docker_command([
        "history",
        image_id,
        "--no-trunc",
        "--format",
        "{{json .}}",
    ])
    return list(_parse_json_lines(output))


def list_containers(all_containers: bool = False) -> List[Dict[str, object]]:
    args = ["ps", "--format", "{{json .}}"]
    if all_containers:
        args.insert(1, "-a")
    output = _run_docker_command(args)
    return list(_parse_json_lines(output))


def inspect_container(container_id: str) -> Dict[str, object]:
    output = _run_docker_command(["inspect", container_id])
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Failed to parse docker inspect output for {container_id}") from exc
    if not data:
        raise RuntimeError(f"docker inspect returned no data for container {container_id}")
    return data[0]


def _format_bytes(num_bytes: int) -> str:
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for suffix in suffixes:
        if value < 1024.0:
            return f"{value:.1f} {suffix}"
        value /= 1024.0
    return f"{value:.1f} PB"


def analyze_image(image: Dict[str, object]) -> List[Recommendation]:
    recs: List[Recommendation] = []
    image_id = str(image.get("ID"))
    repo_tags = image.get("Repository") or image.get("RepositoryName") or "<none>"
    tag = image.get("Tag") or image.get("TagName") or "<none>"
    subject = f"image {repo_tags}:{tag} ({image_id})"
    try:
        metadata = inspect_image(image_id)
    except RuntimeError as exc:
        return [Recommendation(subject=subject, severity="error", message=str(exc))]

    size_bytes = int(metadata.get("Size", 0))
    if size_bytes > 500 * 1024 * 1024:
        recs.append(
            Recommendation(
                subject,
                "info",
                (
                    "Image size exceeds 500MB ("
                    f"{_format_bytes(size_bytes)}). Consider multi-stage builds,"
                    " removing build tools, and pruning package caches."
                ),
            )
        )

    root_fs = metadata.get("RootFS", {})
    layers = root_fs.get("Layers") or []
    if isinstance(layers, list) and len(layers) > 20:
        recs.append(
            Recommendation(
                subject,
                "info",
                (
                    f"Image has {len(layers)} layers; consolidating RUN instructions or"
                    " leveraging multi-stage builds can reduce layer count and size."
                ),
            )
        )

    config = metadata.get("Config", {})
    user = config.get("User") or "root"
    if user in ("", "root"):
        recs.append(
            Recommendation(
                subject,
                "warning",
                "Container runs as root by default. Define a non-root user for improved security.",
            )
        )

    if not config.get("Healthcheck"):
        recs.append(
            Recommendation(
                subject,
                "suggestion",
                "No HEALTHCHECK configured. Add one to detect unhealthy containers at runtime.",
            )
        )

    exposed_ports = config.get("ExposedPorts") or {}
    if exposed_ports and not config.get("Labels", {}).get("org.opencontainers.image.source"):
        recs.append(
            Recommendation(
                subject,
                "info",
                "Expose ports with clear metadata (labels like org.opencontainers.image.source) to aid SBOM tracking.",
            )
        )

    env_vars = config.get("Env") or []
    env_dict = {env.split("=", 1)[0]: env.split("=", 1)[1] for env in env_vars if "=" in env}
    if "PYTHONUNBUFFERED" not in env_dict and any("python" in str(cmd).lower() for cmd in (config.get("Cmd") or [])):
        recs.append(
            Recommendation(
                subject,
                "suggestion",
                "Set PYTHONUNBUFFERED=1 to improve logging responsiveness for Python applications.",
            )
        )

    if env_dict.get("PIP_NO_CACHE_DIR") not in ("1", "true", "True"):
        recs.append(
            Recommendation(
                subject,
                "info",
                "Enable PIP_NO_CACHE_DIR=1 to avoid persisting pip caches inside the image.",
            )
        )

    history = image_history(image_id)
    large_layers = [
        layer for layer in history if layer.get("Size") and layer["Size"] not in ("0B", "0 B")
    ]
    for layer in large_layers:
        size_str = str(layer.get("Size"))
        try:
            size_value, unit = size_str.split()
            size_value = float(size_value)
        except ValueError:
            continue
        if unit.upper().startswith("GB") or (unit.upper().startswith("MB") and size_value > 200):
            created_by = str(layer.get("CreatedBy", "<unknown>"))
            recs.append(
                Recommendation(
                    subject,
                    "info",
                    (
                        f"Layer created by '{created_by}' is large ({size_str}). "
                        "Break the command into smaller steps or clean temporary artifacts to shrink the layer."
                    ),
                )
            )

    if not recs:
        recs.append(Recommendation(subject, "ok", "No issues detected for this image."))
    return recs


def analyze_container(container: Dict[str, object]) -> List[Recommendation]:
    recs: List[Recommendation] = []
    container_id = str(container.get("ID"))
    name = container.get("Names") or container.get("Name") or "<unnamed>"
    subject = f"container {name} ({container_id})"

    try:
        metadata = inspect_container(container_id)
    except RuntimeError as exc:
        return [Recommendation(subject=subject, severity="error", message=str(exc))]

    state = metadata.get("State", {})
    if not state.get("Running", False):
        recs.append(
            Recommendation(subject, "warning", "Container is not running. Review recent exit codes for stability issues."),
        )
    elif state.get("Health") and state["Health"].get("Status") != "healthy":
        recs.append(
            Recommendation(
                subject,
                "warning",
                f"Container health status is {state['Health']['Status']}. Investigate failing health checks.",
            )
        )

    config = metadata.get("Config", {})
    user = config.get("User") or "root"
    if user in ("", "root"):
        recs.append(
            Recommendation(
                subject,
                "warning",
                "Container is running as root. Use a non-root user or user namespace remapping for better security.",
            )
        )

    host_config = metadata.get("HostConfig", {})
    restart_policy = (host_config.get("RestartPolicy") or {}).get("Name") or ""
    if restart_policy in ("", "no"):
        recs.append(
            Recommendation(
                subject,
                "suggestion",
                "No restart policy configured. Consider using --restart unless-stopped for resilient workloads.",
            )
        )

    if host_config.get("Privileged"):
        recs.append(
            Recommendation(
                subject,
                "warning",
                "Container is running in privileged mode. Drop to least privileges whenever possible.",
            )
        )

    if not host_config.get("Memory"):
        recs.append(
            Recommendation(
                subject,
                "info",
                "No memory limit set. Configure --memory to avoid node contention and improve stability.",
            )
        )

    if host_config.get("LogConfig", {}).get("Type") in ("", "json-file"):
        recs.append(
            Recommendation(
                subject,
                "suggestion",
                "Default logging driver json-file can grow unbounded. Configure max-size/max-file or switch to centralized logging.",
            )
        )

    network_settings = metadata.get("NetworkSettings", {})
    if network_settings.get("Ports") and any(details is None for details in network_settings["Ports"].values()):
        recs.append(
            Recommendation(
                subject,
                "info",
                "Container exposes ports without host bindings. Ensure proper network policies are enforced.",
            )
        )

    if not recs:
        recs.append(Recommendation(subject, "ok", "No runtime issues detected for this container."))
    return recs


def render_report(recommendations: Iterable[Recommendation]) -> None:
    for rec in recommendations:
        print(f"[{rec.severity.upper():9}] {rec.subject}: {rec.message}")


def analyze_once(args: argparse.Namespace) -> None:
    if args.images:
        try:
            images = list_images()
        except DockerUnavailableError as exc:
            print(str(exc), file=sys.stderr)
            return
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return
        for image in images:
            render_report(analyze_image(image))

    if args.containers:
        try:
            containers = list_containers(all_containers=args.all_containers)
        except DockerUnavailableError as exc:
            print(str(exc), file=sys.stderr)
            return
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return
        if not containers:
            print("No containers found.")
        for container in containers:
            render_report(analyze_container(container))


def watch_mode(args: argparse.Namespace) -> None:
    interval = args.watch
    if interval <= 0:
        print("Watch interval must be greater than zero seconds.", file=sys.stderr)
        return
    try:
        while True:
            print(time.strftime("\n=== %Y-%m-%d %H:%M:%S ==="))
            analyze_once(args)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping watch mode.")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze Docker images and containers for optimization opportunities.",
    )
    parser.add_argument(
        "--images",
        action="store_true",
        help="Analyze local Docker images for size, security, and performance issues.",
    )
    parser.add_argument(
        "--containers",
        action="store_true",
        help="Analyze Docker containers (default: running only).",
    )
    parser.add_argument(
        "--all-containers",
        action="store_true",
        help="Inspect stopped containers as well (implies --containers).",
    )
    parser.add_argument(
        "--watch",
        type=int,
        default=0,
        help="Continuously analyze at the provided interval in seconds.",
    )
    args = parser.parse_args(argv)

    if args.all_containers:
        args.containers = True

    if not args.images and not args.containers:
        # default to analyzing both images and running containers
        args.images = True
        args.containers = True

    return args


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    if args.watch:
        watch_mode(args)
    else:
        analyze_once(args)


if __name__ == "__main__":
    main()
