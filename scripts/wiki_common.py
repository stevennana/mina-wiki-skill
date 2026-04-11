#!/usr/bin/env python3
"""Shared helpers for Steven Wiki skill scripts."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_ENV_VAR = "STEVEN_WIKI_CONFIG"
DEFAULT_CONFIG_NAME = ".steven-wiki.json"
SYNC_METADATA_DIR = ".steven-wiki"
SYNC_METADATA_NAME = "last_sync.json"
WIKI_PAGE_DIRS = ("sources", "entities", "concepts", "analyses")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "with",
}


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
    try:
        branch = run_git(raw_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    except ConfigError:
        branch = run_git(raw_dir, ["symbolic-ref", "--short", "HEAD"])

    try:
        head = run_git(raw_dir, ["rev-parse", "HEAD"])
        short_head = head[:7]
        has_commits = True
    except ConfigError:
        head = None
        short_head = "unborn"
        has_commits = False

    status_short = run_git(raw_dir, ["status", "--short"])
    changed_files = [line[3:] for line in status_short.splitlines() if len(line) >= 4]
    return {
        "branch": branch,
        "head": head,
        "short_head": short_head,
        "has_commits": has_commits,
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
    baseline_commit_recommended = not snapshot["has_commits"]
    follow_up_actions: list[str] = []
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

    if baseline_commit_recommended:
        reasons.append(
            "Raw repository has no baseline commit yet. After the initial wiki sync is complete, "
            "create a raw baseline commit so future wiki refreshes can rely on git history."
        )
        follow_up_actions.append(
            "After the wiki reflects the current raw tree, create the first commit in WIKI_RAW_DIR."
        )

    return {
        "raw": snapshot,
        "wiki_sync": metadata,
        "needs_sync": needs_sync,
        "reasons": reasons,
        "baseline_commit_recommended": baseline_commit_recommended,
        "follow_up_actions": follow_up_actions,
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


def slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^\w\s/-]", "", text)
    text = text.replace("/", "-")
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-") or "untitled"


def titleize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def safe_relative_to(path: Path, root: Path) -> Path:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ConfigError(f"Path {resolved_path} is outside root {resolved_root}") from exc


def resolve_raw_input(raw_dir: Path, raw_input: str) -> Path:
    candidate = Path(raw_input)
    if not candidate.is_absolute():
        candidate = raw_dir / candidate
    candidate = candidate.expanduser().resolve()
    safe_relative_to(candidate, raw_dir)
    return candidate


def is_probably_text_file(path: Path) -> bool:
    return path.suffix.lower() in {
        ".md",
        ".markdown",
        ".txt",
        ".text",
        ".rst",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".log",
        ".xml",
        ".html",
        ".htm",
    }


def read_raw_text(path: Path) -> tuple[str, bool]:
    if is_probably_text_file(path):
        try:
            return path.read_text(encoding="utf-8"), True
        except UnicodeDecodeError:
            pass
    return f"Binary or unsupported raw source: {path.name}", False


def source_page_slug(raw_relative: Path) -> str:
    return slugify(str(raw_relative.with_suffix("")))


def source_page_path(wiki_dir: Path, raw_relative: Path) -> Path:
    return wiki_dir / "sources" / f"{source_page_slug(raw_relative)}.md"


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    frontmatter_text = text[4:end]
    body = text[end + 5 :]
    metadata: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in frontmatter_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_list_key:
            metadata.setdefault(current_list_key, []).append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            metadata[key] = []
            current_list_key = key
        else:
            metadata[key] = value.strip("'\"")
            current_list_key = None
    return metadata, body.lstrip("\n")


def dump_frontmatter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def read_wiki_page(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    return parse_frontmatter(text)


def write_wiki_page(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = dump_frontmatter(metadata) + "\n\n" + body.strip() + "\n"
    path.write_text(content, encoding="utf-8")


def iter_wiki_pages(wiki_dir: Path) -> list[Path]:
    pages: list[Path] = []
    for directory in WIKI_PAGE_DIRS:
        root = wiki_dir / directory
        if root.exists():
            pages.extend(sorted(root.rglob("*.md")))
    return pages


def wiki_page_ref(path: Path, wiki_dir: Path) -> str:
    relative = safe_relative_to(path, wiki_dir)
    return str(relative.with_suffix("")).replace("\\", "/")


def extract_wiki_links(text: str) -> list[str]:
    return re.findall(r"\[\[([^\]]+)\]\]", text)


def extract_summary(body: str) -> str:
    match = re.search(r"## Summary\s+(.*?)(?:\n## |\Z)", body, re.S)
    if match:
        lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
        if lines:
            return lines[0]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    return [token for token in tokens if token not in STOPWORDS]


def extract_keywords(text: str, limit: int = 5) -> list[str]:
    counts: dict[str, int] = {}
    for token in tokenize(text):
        counts[token] = counts.get(token, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _count in ordered[:limit]]


def extract_entity_terms(text: str, limit: int = 3) -> list[str]:
    pattern = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z0-9]+){0,2})\b", text)
    seen: list[str] = []
    for term in pattern:
        cleaned = term.strip()
        if cleaned.lower() in STOPWORDS:
            continue
        if cleaned not in seen:
            seen.append(cleaned)
        if len(seen) >= limit:
            break
    return seen


def choose_related_terms(title: str, content: str) -> dict[str, list[str]]:
    keywords = [term for term in extract_keywords(f"{title}\n{content}", limit=4) if term not in {"summary", "source"}]
    entities = extract_entity_terms(content or title, limit=3)
    return {"concepts": keywords, "entities": entities}


def now_iso_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
