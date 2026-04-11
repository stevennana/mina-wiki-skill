#!/usr/bin/env python3
"""Validate raw/wiki directories for the Steven Wiki skill."""

from __future__ import annotations

import json
import sys

from wiki_common import ConfigError, resolve_paths, validate_paths


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    payload = {
        "ok": not errors,
        "source": paths.source,
        "config_path": str(paths.config_path) if paths.config_path else None,
        "raw_dir": str(paths.raw_dir),
        "wiki_dir": str(paths.wiki_dir),
        "errors": errors,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
