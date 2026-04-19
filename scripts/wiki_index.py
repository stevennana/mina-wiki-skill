#!/usr/bin/env python3
"""Rebuild wiki indexes from current pages and taxonomy metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    build_directory_index_text,
    build_root_index_text,
    extract_summary,
    read_wiki_page,
    resolve_paths,
    resolve_taxonomy,
    safe_relative_to,
    validate_paths,
    wiki_page_ref,
)


def discover_section_dirs(wiki_dir: Path) -> list[Path]:
    directories: list[Path] = []
    for path in sorted(wiki_dir.rglob("*")):
        if not path.is_dir():
            continue
        rel = safe_relative_to(path, wiki_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        directories.append(path)
    return directories


def list_leaf_pages(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.md") if path.name != "index.md")


def build_directory_entries(wiki_dir: Path, directory: Path) -> list[str]:
    lines: list[str] = []
    subdirs = sorted(path for path in directory.iterdir() if path.is_dir() and not path.name.startswith("."))
    if subdirs:
        lines.extend(["## Subsections", ""])
        for child in subdirs:
            lines.append(f"- [[{wiki_page_ref(child / 'index.md', wiki_dir)}]]")
        lines.append("")

    leaf_pages = list_leaf_pages(directory)
    if leaf_pages:
        lines.extend(["## Pages", ""])
        for page in leaf_pages:
            metadata, body = read_wiki_page(page)
            summary = metadata.get("summary") or extract_summary(body) or "No summary yet."
            lines.append(f"- [[{wiki_page_ref(page, wiki_dir)}]]: {summary}")
        lines.append("")
    return lines


def write_index(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def rebuild_indexes(wiki_dir: Path, taxonomy: dict[str, object]) -> list[str]:
    touched: list[str] = []
    root_index = wiki_dir / "index.md"
    write_index(root_index, build_root_index_text(taxonomy))
    touched.append(str(root_index.relative_to(wiki_dir)))

    descriptions = taxonomy.get("section_descriptions", {})
    for directory in discover_section_dirs(wiki_dir):
        rel = safe_relative_to(directory, wiki_dir)
        description = descriptions.get(str(rel).replace("\\", "/"))
        base = build_directory_index_text(str(rel).replace("\\", "/"), description).splitlines()
        base.extend(build_directory_entries(wiki_dir, directory))
        index_path = directory / "index.md"
        write_index(index_path, "\n".join(base))
        touched.append(str(index_path.relative_to(wiki_dir)))

    return touched


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        taxonomy = resolve_taxonomy(paths)
        touched = rebuild_indexes(paths.wiki_dir, taxonomy)
        print(json.dumps({"ok": True, "touched": touched}, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
