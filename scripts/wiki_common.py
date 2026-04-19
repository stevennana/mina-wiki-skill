#!/usr/bin/env python3
"""Shared helpers for mina-wiki-skill scripts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any


CONFIG_ENV_VAR = "MINA_WIKI_CONFIG"
LEGACY_CONFIG_ENV_VAR = "STEVEN_WIKI_CONFIG"
TAXONOMY_ENV_VAR = "WIKI_TAXONOMY_CONFIG"
DEFAULT_CONFIG_NAME = ".mina-wiki.json"
SYNC_METADATA_DIR = ".mina-wiki"
SYNC_METADATA_NAME = "last_sync.json"
SOURCE_MAP_NAME = "source_map.json"
WIKI_LOCAL_TAXONOMY = "taxonomy.json"
SPECIAL_ROOT_SECTIONS = ("sources", "analyses", "legacy")

FALLBACK_TAXONOMY: dict[str, Any] = {
    "root_sections": ["topics", "analyses", "sources", "legacy"],
    "section_descriptions": {
        "topics": "Maintained project knowledge organized into stable topics.",
        "analyses": "Syntheses, troubleshooting notes, and filed answers.",
        "sources": "Raw-source summaries backing the maintained wiki.",
        "legacy": "Archived material retained during restructures.",
    },
    "children": {},
    "default_destination": "topics",
    "routing_rules": [],
}

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
BOILERPLATE_LINES = {
    "---",
    "skip to main content",
    "account",
    "all files",
    "settings",
    "logout",
    "filter:",
    "submit search",
    "provide feedback",
    "products",
    "company",
    "developers",
    "support",
    "contact us",
}
NOISY_TOKENS = {
    "all",
    "can",
    "com",
    "content",
    "default",
    "div",
    "docs",
    "for",
    "help",
    "html",
    "htm",
    "images",
    "last",
    "not",
    "see",
    "should",
    "shows",
    "using",
    "yes",
    "you",
    "your",
}
GENERIC_TITLE_PREFIXES = {
    "about",
    "accessing",
    "adding",
    "administering",
    "assigning",
    "building",
    "changing",
    "choosing",
    "clearing",
    "cloning",
    "configuring",
    "connecting",
    "consuming",
    "creating",
    "deleting",
    "deploying",
    "designing",
    "enabling",
    "exploring",
    "gathering",
    "getting",
    "initializing",
    "installing",
    "leveraging",
    "logging",
    "maintaining",
    "managing",
    "monitoring",
    "powering",
    "receiving",
    "reviewing",
    "sending",
    "serializing",
    "setting",
    "trying",
    "understanding",
    "upgrading",
    "using",
    "what",
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
    env_path = os.environ.get(CONFIG_ENV_VAR) or os.environ.get(LEGACY_CONFIG_ENV_VAR)
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


def _load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return _load_json(path)


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


def read_project_config(paths: ResolvedPaths | None = None, start_dir: Path | None = None) -> dict[str, Any]:
    if paths and paths.config_path and paths.config_path.exists():
        return _load_json(paths.config_path)
    config_path = discover_config(start_dir)
    if config_path and config_path.exists():
        return _load_json(config_path)
    return {}


def _normalize_path_fragment(value: str) -> str:
    cleaned = value.strip().strip("/")
    cleaned = cleaned.replace("\\", "/")
    cleaned = re.sub(r"/+", "/", cleaned)
    if cleaned.startswith("."):
        raise ConfigError(f"Invalid taxonomy path: {value}")
    return cleaned


def _normalize_taxonomy(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(FALLBACK_TAXONOMY)
    base["section_descriptions"] = dict(FALLBACK_TAXONOMY["section_descriptions"])
    base["children"] = {}
    base["routing_rules"] = []
    if raw:
        for key, value in raw.items():
            base[key] = value

    roots = []
    for section in base.get("root_sections", []):
        normalized = _normalize_path_fragment(str(section))
        if normalized and normalized not in roots:
            roots.append(normalized)
    for required in SPECIAL_ROOT_SECTIONS:
        if required not in roots:
            roots.append(required)
    if not roots:
        roots = list(FALLBACK_TAXONOMY["root_sections"])
    base["root_sections"] = roots

    descriptions: dict[str, str] = {}
    for key, value in dict(base.get("section_descriptions", {})).items():
        descriptions[_normalize_path_fragment(str(key))] = str(value).strip()
    for root in roots:
        descriptions.setdefault(root, f"Maintained wiki section for {root.replace('-', ' ')}.")
    base["section_descriptions"] = descriptions

    children: dict[str, list[str]] = {}
    for parent, items in dict(base.get("children", {})).items():
        parent_key = _normalize_path_fragment(str(parent))
        child_list: list[str] = []
        for item in items or []:
            child_name = _normalize_path_fragment(str(item))
            if "/" in child_name:
                raise ConfigError("taxonomy.children values must be child directory names, not nested paths.")
            if child_name not in child_list:
                child_list.append(child_name)
        children[parent_key] = child_list
    base["children"] = children

    default_destination = _normalize_path_fragment(str(base.get("default_destination") or "topics"))
    if default_destination not in roots and default_destination.split("/")[0] not in roots:
        roots.append(default_destination.split("/")[0])
        descriptions.setdefault(default_destination.split("/")[0], "Maintained wiki section.")
    base["default_destination"] = default_destination
    base["root_sections"] = roots

    rules: list[dict[str, str]] = []
    for item in base.get("routing_rules", []) or []:
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern", "")).strip()
        destination = _normalize_path_fragment(str(item.get("destination", "")).strip())
        if not pattern or not destination:
            continue
        match = str(item.get("match", "any")).strip().lower()
        if match not in {"title", "path", "content", "any"}:
            raise ConfigError(f"Invalid routing rule match target: {match}")
        rules.append({"pattern": pattern, "destination": destination, "match": match})
    base["routing_rules"] = rules
    return base


def resolve_taxonomy(paths: ResolvedPaths | None = None) -> dict[str, Any]:
    paths = paths or resolve_paths()
    config = read_project_config(paths)

    taxonomy_path_env = os.environ.get(TAXONOMY_ENV_VAR)
    if taxonomy_path_env:
        return _normalize_taxonomy(_load_json(Path(taxonomy_path_env).expanduser().resolve()))

    inline_taxonomy = config.get("taxonomy")
    if isinstance(inline_taxonomy, dict):
        return _normalize_taxonomy(inline_taxonomy)

    taxonomy_config_path = config.get("taxonomy_config")
    if taxonomy_config_path:
        return _normalize_taxonomy(_load_json(Path(str(taxonomy_config_path)).expanduser().resolve()))

    local_taxonomy_path = paths.wiki_dir / SYNC_METADATA_DIR / WIKI_LOCAL_TAXONOMY
    local_taxonomy = _load_optional_json(local_taxonomy_path)
    if local_taxonomy:
        return _normalize_taxonomy(local_taxonomy)

    return _normalize_taxonomy(None)


def taxonomy_directory_paths(taxonomy: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    queue = list(taxonomy["root_sections"])
    while queue:
        current = queue.pop(0)
        current = _normalize_path_fragment(current)
        if current in seen:
            continue
        seen.append(current)
        for child in taxonomy.get("children", {}).get(current, []):
            queue.append(f"{current}/{child}")
    return seen


def write_taxonomy_metadata(wiki_dir: Path, taxonomy: dict[str, Any]) -> Path:
    metadata_dir = wiki_dir / SYNC_METADATA_DIR
    metadata_dir.mkdir(parents=True, exist_ok=True)
    path = metadata_dir / WIKI_LOCAL_TAXONOMY
    path.write_text(json.dumps(taxonomy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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
    if not is_git_repo(raw_dir):
        changed_files = [str(path.relative_to(raw_dir)) for path in sorted(raw_dir.rglob("*")) if path.is_file()]
        return {
            "branch": None,
            "head": None,
            "short_head": "no-git",
            "has_commits": False,
            "git_enabled": False,
            "dirty": False,
            "status_short": [],
            "changed_files": changed_files,
        }

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
        "git_enabled": True,
        "dirty": bool(status_short),
        "status_short": status_short.splitlines(),
        "changed_files": changed_files,
    }


def sync_metadata_path(wiki_dir: Path) -> Path:
    return wiki_dir / SYNC_METADATA_DIR / SYNC_METADATA_NAME


def source_map_path(wiki_dir: Path) -> Path:
    return wiki_dir / SYNC_METADATA_DIR / SOURCE_MAP_NAME


def read_sync_metadata(wiki_dir: Path) -> dict[str, Any] | None:
    path = sync_metadata_path(wiki_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Sync metadata is not valid JSON: {path}") from exc


def read_source_map(wiki_dir: Path) -> dict[str, str]:
    path = source_map_path(wiki_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Source map is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"Source map must be a JSON object: {path}")
    return {str(key): str(value) for key, value in payload.items()}


def write_source_map(wiki_dir: Path, mapping: dict[str, str]) -> Path:
    ensure_wiki_structure(wiki_dir)
    path = source_map_path(wiki_dir)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def is_hidden_wiki_path(relative: Path) -> bool:
    return any(part.startswith(".") for part in relative.parts)


def existing_source_pages(wiki_dir: Path) -> list[Path]:
    sources_dir = wiki_dir / "sources"
    if not sources_dir.exists():
        return []
    return sorted(path for path in sources_dir.rglob("*.md") if path.name != "index.md")


def compute_sync_status(paths: ResolvedPaths) -> dict[str, Any]:
    snapshot = git_snapshot(paths.raw_dir)
    metadata = read_sync_metadata(paths.wiki_dir)
    source_map = read_source_map(paths.wiki_dir)
    source_pages = existing_source_pages(paths.wiki_dir)
    baseline_commit_recommended = snapshot["git_enabled"] and not snapshot["has_commits"]
    follow_up_actions: list[str] = []
    if metadata is None:
        needs_sync = True
        reasons = ["No sync metadata found in wiki."]
    else:
        reasons = []
        if metadata.get("raw_head") != snapshot["head"]:
            reasons.append("Raw git HEAD differs from last recorded sync.")
        if snapshot["git_enabled"] and snapshot["dirty"]:
            reasons.append("Raw repository has uncommitted changes.")
        needs_sync = bool(reasons)

    if snapshot["changed_files"] and not source_pages:
        reasons.append("Wiki source pages are missing for the current raw material.")
        needs_sync = True
    elif source_map and not source_pages:
        reasons.append("Source map exists but generated wiki source pages are missing.")
        needs_sync = True

    if baseline_commit_recommended:
        reasons.append(
            "Raw repository has no baseline commit yet. After the initial wiki sync is complete, "
            "create a raw baseline commit so future wiki refreshes can rely on git history."
        )
        follow_up_actions.append(
            "After the wiki reflects the current raw tree, create the first commit in WIKI_RAW_DIR."
        )
    if not snapshot["git_enabled"]:
        reasons.append(
            "Raw directory is not a git repository. Sync can still build the wiki, but freshness tracking is limited to helper metadata."
        )
        follow_up_actions.append(
            "If you want future freshness checks to use git history, run python3 scripts/raw_git_init.py after the initial wiki bootstrap."
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


def build_root_index_text(taxonomy: dict[str, Any]) -> str:
    lines = [
        "---",
        "title: Index",
        "type: index",
        "domain: .",
        "tags:",
        "  - index",
        "---",
        "",
        "# Wiki",
        "",
        "## Summary",
        "",
        "This wiki is organized into maintained sections. Start from the section that matches your current question or workflow, then drill into the relevant sub-indexes and leaf pages.",
        "",
        "## Main Sections",
        "",
    ]
    for section in taxonomy["root_sections"]:
        if section == "legacy":
            continue
        description = taxonomy["section_descriptions"].get(section, f"Maintained wiki section for {section}.")
        lines.append(f"- [[{section}/index]]: {description}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This skill manages a general-purpose wiki. Section names and nested taxonomy may come from project config or wiki-local metadata rather than built-in domain assumptions.",
            "",
        ]
    )
    return "\n".join(lines)


def build_directory_index_text(relative_dir: str, description: str | None = None) -> str:
    title = " ".join(part.replace("-", " ").replace("_", " ").title() for part in Path(relative_dir).parts)
    summary = description or f"Index for the `{relative_dir}` section."
    lines = [
        "---",
        f"title: {title}",
        "type: index",
        f"domain: {relative_dir}",
        "---",
        "",
        f"# {title}",
        "",
        "## Summary",
        "",
        summary,
        "",
    ]
    return "\n".join(lines)


def ensure_wiki_structure(wiki_dir: Path, taxonomy: dict[str, Any] | None = None) -> None:
    wiki_dir.mkdir(parents=True, exist_ok=True)
    taxonomy = taxonomy or resolve_taxonomy(ResolvedPaths(raw_dir=Path("."), wiki_dir=wiki_dir, config_path=None, source="implicit"))
    (wiki_dir / SYNC_METADATA_DIR).mkdir(parents=True, exist_ok=True)
    write_taxonomy_metadata(wiki_dir, taxonomy)

    for relative_dir in taxonomy_directory_paths(taxonomy):
        (wiki_dir / relative_dir).mkdir(parents=True, exist_ok=True)

    root_index = wiki_dir / "index.md"
    if not root_index.exists():
        root_index.write_text(build_root_index_text(taxonomy) + "\n", encoding="utf-8")

    for relative_dir in taxonomy_directory_paths(taxonomy):
        index_path = wiki_dir / relative_dir / "index.md"
        if not index_path.exists():
            description = taxonomy["section_descriptions"].get(relative_dir)
            index_path.write_text(build_directory_index_text(relative_dir, description) + "\n", encoding="utf-8")

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
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^\w\s/-]", "", text)
    text = text.replace("/", "-")
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-") or "untitled"


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


def iter_wiki_pages(wiki_dir: Path, include_indexes: bool = True) -> list[Path]:
    pages: list[Path] = []
    for path in sorted(wiki_dir.rglob("*.md")):
        rel = safe_relative_to(path, wiki_dir)
        if is_hidden_wiki_path(rel):
            continue
        if path.name == "log.md":
            continue
        if not include_indexes and path.name == "index.md":
            continue
        pages.append(path)
    return pages


def wiki_page_ref(path: Path, wiki_dir: Path) -> str:
    relative = safe_relative_to(path, wiki_dir)
    return str(relative.with_suffix("")).replace("\\", "/")


def is_index_ref(ref: str) -> bool:
    return ref == "index" or ref.endswith("/index")


def is_source_ref(ref: str) -> bool:
    return ref.startswith("sources/")


def is_legacy_ref(ref: str) -> bool:
    return ref.startswith("legacy/")


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
    return [token for token in tokens if token not in STOPWORDS and token not in NOISY_TOKENS]


def now_iso_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalize_raw_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(r"<script\b.*?</script>", " ", normalized, flags=re.S | re.I)
    normalized = re.sub(r"<style\b.*?</style>", " ", normalized, flags=re.S | re.I)
    normalized = re.sub(r"<!--.*?-->", " ", normalized, flags=re.S)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = unescape(normalized)
    cleaned_lines: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        lower_line = line.lower()
        if not line:
            continue
        if lower_line in BOILERPLATE_LINES:
            continue
        if lower_line.startswith("documentation coverage"):
            continue
        if lower_line.startswith("last updated:"):
            continue
        if lower_line.startswith("copyright") or lower_line.startswith("©"):
            continue
        if lower_line == "placeholder":
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def extract_title_and_summary(raw_path: Path, text: str) -> tuple[str, str]:
    cleaned = normalize_raw_text(text)
    raw_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    heading = next((line[2:].strip() for line in raw_lines if line.startswith("# ")), "")
    title = heading or raw_path.stem.replace("_", " ").replace("-", " ").strip() or raw_path.name

    summary = ""
    for line in raw_lines:
        if re.match(r"^#{1,6}\s+", line):
            continue
        if line.lower() == title.lower():
            continue
        if len(line) < 20:
            continue
        if re.fullmatch(r"\|?\s*(\[\]\([^)]+\)\s*\|?\s*)+", line):
            continue
        if re.fullmatch(r"[|:\- ]+", line):
            continue
        summary = line
        break
    if not summary:
        summary = f"Raw source {raw_path.name}"
    return title, summary[:240]


def extract_key_points(text: str, title: str, limit: int = 5) -> list[str]:
    cleaned = normalize_raw_text(text)
    candidates: list[str] = []
    seen: set[str] = set()
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("# "):
            continue
        if stripped.lower() == title.lower():
            continue
        if len(stripped) < 20:
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        candidates.append(stripped)
        if len(candidates) >= limit:
            break
    return candidates


def classify_destination(raw_relative: Path, title: str, content: str, taxonomy: dict[str, Any] | None = None) -> str:
    taxonomy = taxonomy or _normalize_taxonomy(None)
    title_probe = title.lower()
    path_probe = str(raw_relative).lower()
    content_probe = content.lower()
    any_probe = "\n".join([title_probe, path_probe, content_probe])
    for rule in taxonomy.get("routing_rules", []):
        match = rule["match"]
        haystack = {
            "title": title_probe,
            "path": path_probe,
            "content": content_probe,
            "any": any_probe,
        }[match]
        if re.search(rule["pattern"], haystack, re.IGNORECASE):
            return rule["destination"]
    return taxonomy["default_destination"]


def leaf_page_path(wiki_dir: Path, destination_dir: str, title: str) -> Path:
    destination = _normalize_path_fragment(destination_dir)
    return wiki_dir / destination / f"{slugify(title)}.md"
