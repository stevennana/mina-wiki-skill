#!/usr/bin/env python3
"""Rebuild index.md from current wiki pages."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    extract_summary,
    iter_wiki_pages,
    read_wiki_page,
    resolve_paths,
    safe_relative_to,
    validate_paths,
    wiki_page_ref,
)


SECTION_TITLES = {
    "sources": "Sources",
    "entities": "Entities",
    "concepts": "Concepts",
    "analyses": "Analyses",
}


def build_index(wiki_dir: Path) -> str:
    grouped: dict[str, list[str]] = {key: [] for key in SECTION_TITLES}
    for page in iter_wiki_pages(wiki_dir):
        rel = safe_relative_to(page, wiki_dir)
        section = rel.parts[0]
        metadata, body = read_wiki_page(page)
        title = metadata.get("title") or Path(rel).stem.replace("-", " ").title()
        summary = metadata.get("summary") or extract_summary(body) or "No summary yet."
        page_ref = wiki_page_ref(page, wiki_dir)
        grouped[section].append(f"- [[{page_ref}]]: {summary}")

    lines = ["# Index", ""]
    for section, heading in SECTION_TITLES.items():
        lines.append(f"## {heading}")
        entries = grouped[section]
        if entries:
            lines.extend(entries)
        else:
            lines.append(f"- No {section} pages yet.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        index_text = build_index(paths.wiki_dir)
        index_path = paths.wiki_dir / "index.md"
        index_path.write_text(index_text, encoding="utf-8")
        print(json.dumps({"ok": True, "index_path": str(index_path)}, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
