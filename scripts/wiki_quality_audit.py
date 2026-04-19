#!/usr/bin/env python3
"""Audit wiki quality signals that require editorial cleanup."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    is_index_ref,
    is_source_ref,
    iter_wiki_pages,
    read_wiki_page,
    resolve_paths,
    safe_relative_to,
    validate_paths,
    wiki_page_ref,
)


PLACEHOLDER_TOKENS = ("Auto-maintained", "No related pages yet.")


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def build_audit(wiki_dir: Path) -> dict[str, object]:
    placeholder_pages: list[str] = []
    malformed_titles: list[str] = []
    short_leaf_pages: list[str] = []
    analyses_count = 0
    index_has_placeholders = False

    index_path = wiki_dir / "index.md"
    if index_path.exists():
        index_text = index_path.read_text(encoding="utf-8", errors="ignore")
        index_has_placeholders = any(token in index_text for token in PLACEHOLDER_TOKENS)

    for page in iter_wiki_pages(wiki_dir):
        rel = safe_relative_to(page, wiki_dir)
        rel_str = str(rel)
        metadata, body = read_wiki_page(page)
        text = json.dumps(metadata, ensure_ascii=False) + "\n" + body
        if any(token in text for token in PLACEHOLDER_TOKENS):
            placeholder_pages.append(rel_str)
        if "\uf0c1" in rel_str or "\uf0c1" in str(metadata.get("title", "")):
            malformed_titles.append(rel_str)

        ref = wiki_page_ref(page, wiki_dir)
        count = line_count(page)
        if ref.startswith("analyses/") and not is_index_ref(ref):
            analyses_count += 1
        elif not is_index_ref(ref) and not is_source_ref(ref) and count < 15:
            short_leaf_pages.append(rel_str)

    return {
        "placeholder_pages": sorted(placeholder_pages),
        "malformed_titles": sorted(malformed_titles),
        "short_leaf_pages": sorted(short_leaf_pages),
        "analyses_count": analyses_count,
        "index_has_placeholders": index_has_placeholders,
        "passes_editorial_gate": not any(
            [
                placeholder_pages,
                malformed_titles,
                short_leaf_pages,
                analyses_count == 0,
                index_has_placeholders,
            ]
        ),
    }


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        audit = build_audit(paths.wiki_dir)
        print(json.dumps({"ok": True, **audit}, indent=2))
        return 0 if audit["passes_editorial_gate"] else 2
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
