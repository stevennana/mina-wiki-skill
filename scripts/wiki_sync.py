#!/usr/bin/env python3
"""Sync the shared wiki from the current raw directory state."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    append_log_entry,
    ensure_wiki_structure,
    extract_wiki_links,
    git_snapshot,
    now_iso_date,
    read_wiki_page,
    resolve_paths,
    safe_relative_to,
    source_page_path,
    validate_paths,
    wiki_page_ref,
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
    sources_dir = wiki_dir / "sources"
    if not sources_dir.exists():
        return mapping
    for page in sorted(sources_dir.rglob("*.md")):
        metadata, _body = read_wiki_page(page)
        raw_path = metadata.get("raw_path")
        if isinstance(raw_path, str) and raw_path.strip():
            mapping[raw_path] = page
    return mapping


def cleanup_related_pages(wiki_dir: Path, source_ref: str) -> list[str]:
    touched: list[str] = []
    for directory in ("concepts", "entities"):
        root = wiki_dir / directory
        if not root.exists():
            continue
        for page in sorted(root.rglob("*.md")):
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
            if not new_sources and metadata.get("type") in {"concept", "entity"} and not remaining_links:
                page.unlink()
                touched.append(page_ref)
                continue

            metadata["sources"] = new_sources
            metadata["last_reviewed"] = now_iso_date()
            write_wiki_page(page, metadata, new_body)
            touched.append(page_ref)
    return touched


def delete_missing_sources(paths, raw_relatives: set[str]) -> list[str]:
    touched: list[str] = []
    for raw_path, page in existing_source_map(paths.wiki_dir).items():
        if raw_path in raw_relatives:
            continue
        source_ref = wiki_page_ref(page, paths.wiki_dir)
        page.unlink()
        touched.append(str(page.relative_to(paths.wiki_dir)))
        touched.extend(cleanup_related_pages(paths.wiki_dir, source_ref))
    return touched


def rebuild_index(script_dir: Path) -> None:
    subprocess.run(
        ["python3", str(script_dir / "wiki_index.py")],
        check=True,
        capture_output=True,
        text=True,
    )


def reset_generated_content(wiki_dir: Path) -> None:
    for relative in ("sources", "concepts", "entities", "analyses", ".steven-wiki"):
        root = wiki_dir / relative
        if not root.exists():
            continue
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if root.exists():
            root.rmdir()
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

        if args.reset_generated:
            reset_generated_content(paths.wiki_dir)
        ensure_wiki_structure(paths.wiki_dir)
        raw_files = list_raw_files(paths.raw_dir)
        raw_relatives = {str(path) for path in raw_files}
        all_touched: list[str] = []

        for raw_relative in raw_files:
            all_touched.extend(ingest_one(paths, str(raw_relative)))

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
