#!/usr/bin/env python3
"""Migrate flat wiki pages into the hierarchical wiki structure."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    classify_destination,
    ensure_wiki_structure,
    extract_summary,
    leaf_page_path,
    read_wiki_page,
    resolve_paths,
    resolve_taxonomy,
    validate_paths,
    wiki_page_ref,
    write_wiki_page,
)


def rewrite_links(wiki_dir: Path, moved: dict[str, str]) -> list[str]:
    touched: list[str] = []
    for page in sorted(wiki_dir.rglob("*.md")):
        rel = page.relative_to(wiki_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = page.read_text(encoding="utf-8")
        updated = text
        for old_ref, new_ref in moved.items():
            updated = re.sub(rf"\[\[{re.escape(old_ref)}\]\]", f"[[{new_ref}]]", updated)
        if updated != text:
            page.write_text(updated, encoding="utf-8")
            touched.append(str(rel))
    return touched


def migrate_flat_pages(wiki_dir: Path, taxonomy: dict[str, object]) -> dict[str, object]:
    moved: dict[str, str] = {}
    archived: list[str] = []

    for flat_dir in ("concepts", "entities"):
        directory = wiki_dir / flat_dir
        if not directory.exists():
            continue
        for page in sorted(directory.glob("*.md")):
            if page.name == "index.md":
                continue
            metadata, body = read_wiki_page(page)
            title = str(metadata.get("title") or page.stem.replace("-", " ").title())
            summary = metadata.get("summary") or extract_summary(body) or f"{title} was migrated from the legacy flat wiki structure."
            destination_dir = classify_destination(Path(page.name), title, body, taxonomy)
            destination_path = leaf_page_path(wiki_dir, destination_dir, title)
            destination_ref = wiki_page_ref(destination_path, wiki_dir)
            source_refs = metadata.get("sources", [])
            if isinstance(source_refs, str):
                source_refs = [source_refs]
            new_metadata = {
                "type": metadata.get("type", "concept"),
                "title": title,
                "summary": summary,
                "last_reviewed": metadata.get("last_reviewed", ""),
                "sources": source_refs,
            }
            new_body = "\n".join(
                [
                    "## Summary",
                    "",
                    summary,
                    "",
                    "## Migration Note",
                    "",
                    f"This page was migrated from [[legacy/flat/{flat_dir}/{page.stem}]] into [[{destination_ref}]].",
                    "",
                    body.strip(),
                    "",
                ]
            )
            write_wiki_page(destination_path, new_metadata, new_body)

            legacy_path = wiki_dir / "legacy" / "flat" / flat_dir / page.name
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(page), str(legacy_path))
            moved[f"{flat_dir}/{page.stem}"] = destination_ref
            archived.append(str(legacy_path.relative_to(wiki_dir)))

        if directory.exists():
            shutil.rmtree(directory)

    rewritten = rewrite_links(wiki_dir, moved)
    return {"moved": moved, "archived": archived, "rewritten": rewritten}


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        taxonomy = resolve_taxonomy(paths)
        ensure_wiki_structure(paths.wiki_dir, taxonomy)
        payload = migrate_flat_pages(paths.wiki_dir, taxonomy)
        subprocess.run(
            ["python3", str(Path(__file__).resolve().parent / "wiki_index.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        print(json.dumps({"ok": True, **payload}, indent=2))
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
