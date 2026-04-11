#!/usr/bin/env python3
"""Shared helpers for Steven Wiki skill scripts."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_ENV_VAR = "STEVEN_WIKI_CONFIG"
DEFAULT_CONFIG_NAME = ".steven-wiki.json"
SYNC_METADATA_DIR = ".steven-wiki"
SYNC_METADATA_NAME = "last_sync.json"


class ConfigError(RuntimeError):
    """Raised when skill configuration is missing or invalid."""


@dataclass
class ResolvedPaths:
    raw_dir: Path
    wiki_dir: Path
    config_path: Path | None
    source: str


def discover_config(start_dir: Path | None = None) -> Path | None:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        path = Path(env_path).expanduser().resolve()
        return path if path.exists() else path

    current = (start_dir or Path.cwd()).resolve()
    for candidate_dir in [current, *current.parents]:
        candidate = candidate_dir / DEFAULT_CONFIG_NAME
        if candidate.exists():
            return candidate
    return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file is not valid JSON: {path}") from exc


def resolve_paths(start_dir: Path | None = None) -> ResolvedPaths:
    raw_env = os.environ.get("WIKI_RAW_DIR")
    wiki_env = os.environ.get("WIKI_DIR")
    config_path = discover_config(start_dir)
    config: dict[str, Any] = _load_json(config_path) if config_path and config_path.exists() else {}

    raw_value = raw_env or config.get("raw_dir") or config.get("WIKI_RAW_DIR")
    wiki_value = wiki_env or config.get("wiki_dir") or config.get("WIKI_DIR")

    if not raw_value or not wiki_value:
        raise ConfigError(
            "Missing wiki directories. Set WIKI_RAW_DIR and WIKI_DIR or provide them "
            f"in {CONFIG_ENV_VAR} / {DEFAULT_CONFIG_NAME}."
        )

    source = "environment" if raw_env or wiki_env else "config"
    return ResolvedPaths(
        raw_dir=Path(raw_value).expanduser().resolve(),
        wiki_dir=Path(wiki_value).expanduser().resolve(),
        config_path=config_path,
        source=source,
    )


def validate_paths(paths: ResolvedPaths) -> list[str]:
    errors: list[str] = []
    if not paths.raw_dir.exists():
        errors.append(f"Raw directory does not exist: {paths.raw_dir}")
    elif not paths.raw_dir.is_dir():
        errors.append(f"Raw directory is not a directory: {paths.raw_dir}")

    if not paths.wiki_dir.exists():
        errors.append(f"Wiki directory does not exist: {paths.wiki_dir}")
    elif not paths.wiki_dir.is_dir():
        errors.append(f"Wiki directory is not a directory: {paths.wiki_dir}")

    if paths.raw_dir.exists() and not is_git_repo(paths.raw_dir):
        errors.append(f"Raw directory is not a git repository: {paths.raw_dir}")

    if paths.wiki_dir.exists() and not os.access(paths.wiki_dir, os.W_OK):
        errors.append(f"Wiki directory is not writable: {paths.wiki_dir}")

    return errors


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def run_git(path: Path, args: list[str]) -> str:
    command = ["git", *args]
    try:
        completed = subprocess.run(
            command,
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip()
        raise ConfigError(f"git {' '.join(args)} failed in {path}: {stderr}") from exc
    return completed.stdout.strip()


def git_snapshot(raw_dir: Path) -> dict[str, Any]:
    head = run_git(raw_dir, ["rev-parse", "HEAD"])
    branch = run_git(raw_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    status_short = run_git(raw_dir, ["status", "--short"])
    changed_files = [line[3:] for line in status_short.splitlines() if len(line) >= 4]
    return {
        "branch": branch,
        "head": head,
        "short_head": head[:7],
        "dirty": bool(status_short),
        "status_short": status_short.splitlines(),
        "changed_files": changed_files,
    }


def sync_metadata_path(wiki_dir: Path) -> Path:
    return wiki_dir / SYNC_METADATA_DIR / SYNC_METADATA_NAME


def read_sync_metadata(wiki_dir: Path) -> dict[str, Any] | None:
    path = sync_metadata_path(wiki_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Sync metadata is not valid JSON: {path}") from exc


def compute_sync_status(paths: ResolvedPaths) -> dict[str, Any]:
    snapshot = git_snapshot(paths.raw_dir)
    metadata = read_sync_metadata(paths.wiki_dir)
    if metadata is None:
        needs_sync = True
        reasons = ["No sync metadata found in wiki."]
    else:
        reasons = []
        if metadata.get("raw_head") != snapshot["head"]:
            reasons.append("Raw git HEAD differs from last recorded sync.")
        if snapshot["dirty"]:
            reasons.append("Raw repository has uncommitted changes.")
        needs_sync = bool(reasons)

    return {
        "raw": snapshot,
        "wiki_sync": metadata,
        "needs_sync": needs_sync,
        "reasons": reasons,
        "sync_metadata_path": str(sync_metadata_path(paths.wiki_dir)),
    }


def ensure_wiki_structure(wiki_dir: Path) -> None:
    for directory in ["sources", "entities", "concepts", "analyses", SYNC_METADATA_DIR]:
        (wiki_dir / directory).mkdir(parents=True, exist_ok=True)

    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        index_path.write_text("# Index\n\n", encoding="utf-8")

    log_path = wiki_dir / "log.md"
    if not log_path.exists():
        log_path.write_text("# Log\n\n", encoding="utf-8")


def project_context() -> dict[str, str]:
    return {
        "project_dir": str(Path.cwd()),
        "session_id": os.environ.get("CODEX_THREAD_ID", "unknown"),
    }


def append_log_entry(
    wiki_dir: Path,
    operation: str,
    touched: list[str],
    raw_snapshot: dict[str, Any] | None = None,
    note: str | None = None,
) -> str:
    ensure_wiki_structure(wiki_dir)
    context = project_context()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    header = f"## [{timestamp}] {operation} | session={context['session_id']}"
    lines = [header, "", f"- project_dir: `{context['project_dir']}`"]
    if raw_snapshot:
        lines.append(f"- raw_head: `{raw_snapshot['short_head']}`")
    if touched:
        lines.append(f"- touched: {', '.join(f'`{item}`' for item in touched)}")
    if note:
        lines.append(f"- note: {note}")
    lines.append("")
    log_path = wiki_dir / "log.md"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Log\n\n"
    content = existing.rstrip() + "\n\n" + "\n".join(lines) + "\n"
    log_path.write_text(content, encoding="utf-8")
    return header


def write_sync_metadata(wiki_dir: Path, raw_snapshot: dict[str, Any], operation: str) -> Path:
    ensure_wiki_structure(wiki_dir)
    metadata = {
        "raw_head": raw_snapshot["head"],
        "raw_branch": raw_snapshot["branch"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "dirty": raw_snapshot["dirty"],
        "status_short": raw_snapshot["status_short"],
        "project_context": project_context(),
    }
    path = sync_metadata_path(wiki_dir)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
