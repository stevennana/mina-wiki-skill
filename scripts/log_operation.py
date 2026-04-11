#!/usr/bin/env python3
"""Append wiki log entries and optionally update sync metadata."""

from __future__ import annotations

import argparse
import json
import sys

from wiki_common import (
    ConfigError,
    append_log_entry,
    ensure_wiki_structure,
    git_snapshot,
    resolve_paths,
    validate_paths,
    write_sync_metadata,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True, help="Operation name such as ingest, query, or lint.")
    parser.add_argument("--touched", nargs="*", default=[], help="Wiki-relative paths changed by the operation.")
    parser.add_argument("--note", help="Optional short note for the log entry.")
    parser.add_argument(
        "--update-sync-marker",
        action="store_true",
        help="Write sync metadata using the current raw git state after logging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        ensure_wiki_structure(paths.wiki_dir)
        raw_snapshot = git_snapshot(paths.raw_dir)
        header = append_log_entry(paths.wiki_dir, args.operation, args.touched, raw_snapshot, args.note)
        sync_path = None
        if args.update_sync_marker:
            sync_path = str(write_sync_metadata(paths.wiki_dir, raw_snapshot, args.operation))
        print(json.dumps({"ok": True, "log_entry": header, "sync_metadata_path": sync_path}, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
