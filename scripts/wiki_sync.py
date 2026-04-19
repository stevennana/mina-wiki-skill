#!/usr/bin/env python3
"""Sync the shared wiki from the current raw directory state."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    append_log_entry,
    ensure_wiki_structure,
    extract_wiki_links,
    git_snapshot,
    read_source_map,
    read_wiki_page,
    resolve_paths,
    resolve_taxonomy,
    safe_relative_to,
    taxonomy_directory_paths,
    validate_paths,
    wiki_page_ref,
    write_source_map,
    write_sync_metadata,
    write_wiki_page,
)
from wiki_ingest import ingest_one


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-generated", action="store_true")
    parser.add_argument("--update-sync-marker", action="store_true")
    return parser.parse_args()


def list_raw_files(raw_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = safe_relative_to(path, raw_dir)
        if any(part.startswith(".git") for part in rel.parts):
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(rel)
    return files


def existing_source_map(wiki_dir: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for raw_path, page_ref in read_source_map(wiki_dir).items():
        page = wiki_dir / f"{page_ref}.md"
        if page.exists():
            mapping[raw_path] = page
    return mapping


def cleanup_related_pages(wiki_dir: Path, source_ref: str) -> list[str]:
    touched: list[str] = []
    for page in sorted(wiki_dir.rglob("*.md")):
        rel = safe_relative_to(page, wiki_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.parts[0] == "sources" or page.name == "log.md":
            continue
        metadata, body = read_wiki_page(page)
        sources = metadata.get("sources", [])
        if isinstance(sources, str):
            sources = [sources]
        if source_ref not in sources and f"[[{source_ref}]]" not in body:
            continue

        new_sources = [item for item in sources if item != source_ref]
        new_lines = [line for line in body.splitlines() if line.strip() != f"- [[{source_ref}]]"]
        new_body = "\n".join(new_lines).strip() + "\n"
        page_ref = wiki_page_ref(page, wiki_dir)
        remaining_links = [link for link in extract_wiki_links(new_body) if link != source_ref]
        if not new_sources and not remaining_links and not page_ref.endswith("/index") and not page_ref.startswith("analyses/"):
            page.unlink()
            touched.append(page_ref)
            continue

        sources_changed = new_sources != sources
        body_changed = new_body.strip() != body.strip()
        if sources_changed or body_changed:
            metadata["sources"] = new_sources
            write_wiki_page(page, metadata, new_body)
            touched.append(page_ref)
    return touched


def delete_missing_sources(paths, raw_relatives: set[str]) -> list[str]:
    touched: list[str] = []
    source_map = read_source_map(paths.wiki_dir)
    updated_map = dict(source_map)
    for raw_path, page in existing_source_map(paths.wiki_dir).items():
        if raw_path in raw_relatives:
            continue
        source_ref = wiki_page_ref(page, paths.wiki_dir)
        page.unlink()
        touched.append(str(page.relative_to(paths.wiki_dir)))
        touched.extend(cleanup_related_pages(paths.wiki_dir, source_ref))
        updated_map.pop(raw_path, None)
    if updated_map != source_map:
        write_source_map(paths.wiki_dir, updated_map)
    return touched


def rebuild_index(script_dir: Path) -> None:
    subprocess.run(
        ["python3", str(script_dir / "wiki_index.py")],
        check=True,
        capture_output=True,
        text=True,
    )


def reset_generated_content(wiki_dir: Path, taxonomy: dict[str, object]) -> None:
    removable_dirs = taxonomy_directory_paths(taxonomy)
    removable_dirs.append(".mina-wiki")
    for relative in removable_dirs:
        root = wiki_dir / relative
        if root.exists():
            shutil.rmtree(root)
    for relative in ("index.md", "log.md"):
        path = wiki_dir / relative
        if path.exists():
            path.unlink()


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        taxonomy = resolve_taxonomy(paths)
        if args.reset_generated:
            reset_generated_content(paths.wiki_dir, taxonomy)
        ensure_wiki_structure(paths.wiki_dir, taxonomy)
        raw_files = list_raw_files(paths.raw_dir)
        raw_relatives = {str(path) for path in raw_files}
        all_touched: list[str] = []

        for raw_relative in raw_files:
            all_touched.extend(ingest_one(paths, str(raw_relative), taxonomy))

        deleted = delete_missing_sources(paths, raw_relatives)
        all_touched.extend(deleted)

        rebuild_index(Path(__file__).resolve().parent)
        raw_snapshot = git_snapshot(paths.raw_dir)
        note = f"synced={len(raw_files)} deleted={len(deleted)}"
        append_log_entry(paths.wiki_dir, "sync", sorted(set(all_touched)), raw_snapshot, note=note)
        sync_path = None
        if args.update_sync_marker:
            sync_path = str(write_sync_metadata(paths.wiki_dir, raw_snapshot, "sync"))

        payload = {
            "ok": True,
            "synced_raw_files": len(raw_files),
            "deleted_wiki_pages": sorted(set(deleted)),
            "touched": sorted(set(all_touched)),
            "sync_metadata_path": sync_path,
        }
        print(json.dumps(payload, indent=2))
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
