#!/usr/bin/env python3
"""Report whether the shared wiki is behind the raw repository."""

from __future__ import annotations

import json
import sys

from wiki_common import ConfigError, compute_sync_status, resolve_paths, validate_paths


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        payload = {
            "ok": True,
            "raw_dir": str(paths.raw_dir),
            "wiki_dir": str(paths.wiki_dir),
            **compute_sync_status(paths),
        }
        print(json.dumps(payload, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
