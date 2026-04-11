#!/usr/bin/env python3
"""Create the minimal shared wiki structure if it does not already exist."""

from __future__ import annotations

import json
import sys

from wiki_common import ConfigError, ensure_wiki_structure, resolve_paths, validate_paths


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        errors = [error for error in errors if "Wiki directory does not exist" not in error]
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        paths.wiki_dir.mkdir(parents=True, exist_ok=True)
        ensure_wiki_structure(paths.wiki_dir)
        print(
            json.dumps(
                {
                    "ok": True,
                    "wiki_dir": str(paths.wiki_dir),
                    "created": ["sources", "entities", "concepts", "analyses", ".steven-wiki", "index.md", "log.md"],
                },
                indent=2,
            )
        )
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
