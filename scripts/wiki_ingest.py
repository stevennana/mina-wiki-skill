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
    classify_destination,
    ensure_wiki_structure,
    extract_key_points,
    extract_title_and_summary,
    git_snapshot,
    leaf_page_path,
    now_iso_date,
    read_raw_text,
    read_source_map,
    read_wiki_page,
    resolve_paths,
    resolve_taxonomy,
    resolve_raw_input,
    safe_relative_to,
    source_page_path,
    validate_paths,
    wiki_page_ref,
    write_source_map,
    write_sync_metadata,
    write_wiki_page,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_paths", nargs="+", help="Raw file paths relative to WIKI_RAW_DIR.")
    parser.add_argument("--update-sync-marker", action="store_true")
    return parser.parse_args()


def upsert_leaf_page(page_path: Path, title: str, source_ref: str, summary: str) -> bool:
    is_new_page = not page_path.exists()
    if is_new_page:
        metadata = {
            "type": "concept",
            "title": title,
            "last_reviewed": now_iso_date(),
            "sources": [source_ref],
        }
        body = "\n".join(
            [
                "## Summary",
                "",
                summary,
                "",
                "## Source Coverage",
                "",
                f"- [[{source_ref}]]",
                "",
            ]
        )
        write_wiki_page(page_path, metadata, body)
        return True

    metadata, body = read_wiki_page(page_path)
    sources = metadata.get("sources", [])
    if isinstance(sources, str):
        sources = [sources]

    changed = False
    if source_ref not in sources:
        sources.append(source_ref)
        metadata["sources"] = sorted(sources)
        changed = True

    if "## Source Coverage" not in body:
        body = body.rstrip() + "\n\n## Source Coverage\n\n"
        changed = True
    if f"- [[{source_ref}]]" not in body:
        body = body.rstrip() + f"\n- [[{source_ref}]]\n"
        changed = True

    if changed:
        metadata["last_reviewed"] = now_iso_date()
        write_wiki_page(page_path, metadata, body)
    return changed


def rebuild_index(script_dir: Path) -> None:
    subprocess.run(
        ["python3", str(script_dir / "wiki_index.py")],
        check=True,
        capture_output=True,
        text=True,
    )


def ingest_one(paths, raw_input: str, taxonomy: dict[str, object] | None = None) -> list[str]:
    raw_path = resolve_raw_input(paths.raw_dir, raw_input)
    raw_relative = safe_relative_to(raw_path, paths.raw_dir)
    raw_text, is_text = read_raw_text(raw_path)
    source_path = source_page_path(paths.wiki_dir, raw_relative)
    source_ref = wiki_page_ref(source_path, paths.wiki_dir)
    taxonomy = taxonomy or resolve_taxonomy(paths)

    title, summary = extract_title_and_summary(raw_path, raw_text) if is_text else (
        raw_path.stem.replace("_", " ").replace("-", " ").strip() or raw_path.name,
        f"Raw source {raw_path.name}",
    )
    key_points = extract_key_points(raw_text, title, limit=5) if is_text else []
    destination_dir = classify_destination(raw_relative, title, raw_text, taxonomy)
    destination_path = leaf_page_path(paths.wiki_dir, destination_dir, title)
    destination_ref = wiki_page_ref(destination_path, paths.wiki_dir)

    body_lines = [
        "## Summary",
        "",
        summary,
        "",
        "## Key Points",
        "",
    ]
    if key_points:
        body_lines.extend(f"- {line[:220]}" for line in key_points)
    else:
        body_lines.append(f"- Binary or unsupported raw source: `{raw_path.name}`")
    body_lines.extend(
        [
            "",
            "## Maintained Coverage",
            "",
            f"- [[{destination_ref}]]",
            "",
        ]
    )

    touched: list[str] = []
    new_body = "\n".join(body_lines)
    if source_path.exists():
        existing_metadata, existing_body = read_wiki_page(source_path)
        metadata = {
            "type": "source",
            "title": title,
            "summary": summary,
            "last_reviewed": existing_metadata.get("last_reviewed", now_iso_date()),
        }
        if existing_metadata != metadata or existing_body.strip() != new_body.strip():
            metadata["last_reviewed"] = now_iso_date()
            write_wiki_page(source_path, metadata, new_body)
            touched.append(str(source_path.relative_to(paths.wiki_dir)))
    else:
        metadata = {
            "type": "source",
            "title": title,
            "summary": summary,
            "last_reviewed": now_iso_date(),
        }
        write_wiki_page(source_path, metadata, new_body)
        touched.append(str(source_path.relative_to(paths.wiki_dir)))

    if upsert_leaf_page(destination_path, title, source_ref, summary):
        touched.append(str(destination_path.relative_to(paths.wiki_dir)))

    source_mapping = read_source_map(paths.wiki_dir)
    source_mapping[str(raw_relative)] = wiki_page_ref(source_path, paths.wiki_dir)
    write_source_map(paths.wiki_dir, source_mapping)
    return sorted(set(touched))


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        taxonomy = resolve_taxonomy(paths)
        ensure_wiki_structure(paths.wiki_dir, taxonomy)
        all_touched: list[str] = []
        for raw_input in args.raw_paths:
            all_touched.extend(ingest_one(paths, raw_input, taxonomy))

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
