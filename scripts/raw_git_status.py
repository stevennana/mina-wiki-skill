#!/usr/bin/env python3
"""Print raw git status for the Steven Wiki skill."""

from __future__ import annotations

import json
import sys

from wiki_common import ConfigError, git_snapshot, resolve_paths, validate_paths


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        payload = {"ok": True, "raw_dir": str(paths.raw_dir), "git": git_snapshot(paths.raw_dir)}
        print(json.dumps(payload, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
