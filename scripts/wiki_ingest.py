#!/usr/bin/env python3
"""Ingest raw files into the shared wiki."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    append_log_entry,
    choose_related_terms,
    ensure_wiki_structure,
    git_snapshot,
    now_iso_date,
    read_raw_text,
    read_wiki_page,
    resolve_paths,
    resolve_raw_input,
    safe_relative_to,
    source_page_path,
    titleize_slug,
    validate_paths,
    wiki_page_ref,
    write_sync_metadata,
    write_wiki_page,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_paths", nargs="+", help="Raw file paths relative to WIKI_RAW_DIR.")
    parser.add_argument("--update-sync-marker", action="store_true")
    return parser.parse_args()


def update_related_page(page_path: Path, page_type: str, title: str, source_ref: str) -> None:
    if page_path.exists():
        metadata, body = read_wiki_page(page_path)
    else:
        metadata = {
            "type": page_type,
            "title": title,
            "last_reviewed": now_iso_date(),
            "sources": [source_ref],
        }
        body = f"## Summary\n\nAuto-maintained {page_type} page for {title}.\n\n## Links\n\n"

    sources = metadata.get("sources", [])
    if isinstance(sources, str):
        sources = [sources]
    if source_ref not in sources:
        sources.append(source_ref)
    metadata["sources"] = sorted(sources)
    metadata["last_reviewed"] = now_iso_date()

    link_line = f"- [[{source_ref}]]"
    if "## Links" not in body:
        body = body.rstrip() + "\n\n## Links\n\n"
    if link_line not in body:
        body = body.rstrip() + f"\n{link_line}\n"
    write_wiki_page(page_path, metadata, body)


def rebuild_index(script_dir: Path) -> None:
    subprocess.run(
        ["python3", str(script_dir / "wiki_index.py")],
        check=True,
        capture_output=True,
        text=True,
    )


def ingest_one(paths, raw_input: str) -> list[str]:
    raw_path = resolve_raw_input(paths.raw_dir, raw_input)
    raw_relative = safe_relative_to(raw_path, paths.raw_dir)
    raw_text, is_text = read_raw_text(raw_path)
    raw_snapshot = git_snapshot(paths.raw_dir)
    source_path = source_page_path(paths.wiki_dir, raw_relative)
    source_ref = wiki_page_ref(source_path, paths.wiki_dir)

    title = raw_path.stem.replace("_", " ").replace("-", " ").strip() or raw_path.name
    related = choose_related_terms(title, raw_text)

    summary = raw_text.strip().splitlines()[0] if raw_text.strip() else f"Raw source {raw_path.name}"
    summary = summary[:240]
    body_lines = [
        "## Summary",
        "",
        summary,
        "",
        "## Source",
        "",
        f"- raw_path: `{raw_relative}`",
        f"- raw_commit: `{raw_snapshot['short_head']}`",
        f"- text_extractable: `{str(is_text).lower()}`",
        "",
        "## Key Points",
        "",
    ]
    if is_text:
        for line in [line.strip() for line in raw_text.splitlines() if line.strip()][:5]:
            body_lines.append(f"- {line[:220]}")
    else:
        body_lines.append(f"- Binary or unsupported raw source: `{raw_path.name}`")

    related_links: list[str] = []
    touched = [str(source_path.relative_to(paths.wiki_dir))]

    for concept in related["concepts"][:3]:
        slug = concept.lower().replace("_", "-")
        concept_path = paths.wiki_dir / "concepts" / f"{slug}.md"
        update_related_page(concept_path, "concept", titleize_slug(slug), source_ref)
        related_links.append(f"[[{wiki_page_ref(concept_path, paths.wiki_dir)}]]")
        touched.append(str(concept_path.relative_to(paths.wiki_dir)))

    for entity in related["entities"][:2]:
        slug = entity.lower().replace(" ", "-")
        entity_path = paths.wiki_dir / "entities" / f"{slug}.md"
        update_related_page(entity_path, "entity", entity, source_ref)
        related_links.append(f"[[{wiki_page_ref(entity_path, paths.wiki_dir)}]]")
        touched.append(str(entity_path.relative_to(paths.wiki_dir)))

    body_lines.extend(["", "## Related", ""])
    if related_links:
        body_lines.extend(f"- {link}" for link in related_links)
    else:
        body_lines.append("- No related pages yet.")

    metadata = {
        "type": "source",
        "title": title,
        "summary": summary,
        "raw_path": str(raw_relative),
        "last_reviewed": now_iso_date(),
        "raw_commit": raw_snapshot["short_head"],
        "sources": [str(raw_relative)],
    }
    write_wiki_page(source_path, metadata, "\n".join(body_lines))
    return touched


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        ensure_wiki_structure(paths.wiki_dir)
        all_touched: list[str] = []
        for raw_input in args.raw_paths:
            all_touched.extend(ingest_one(paths, raw_input))

        rebuild_index(Path(__file__).resolve().parent)
        raw_snapshot = git_snapshot(paths.raw_dir)
        append_log_entry(paths.wiki_dir, "ingest", sorted(set(all_touched)), raw_snapshot)
        sync_path = None
        if args.update_sync_marker:
            sync_path = str(write_sync_metadata(paths.wiki_dir, raw_snapshot, "ingest"))
        print(json.dumps({"ok": True, "touched": sorted(set(all_touched)), "sync_metadata_path": sync_path}, indent=2))
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
