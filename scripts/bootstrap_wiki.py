#!/usr/bin/env python3
"""Create the minimal configured wiki structure if it does not already exist."""

from __future__ import annotations

import json
import sys

from wiki_common import (
    ConfigError,
    ensure_wiki_structure,
    resolve_paths,
    resolve_taxonomy,
    taxonomy_directory_paths,
    validate_paths,
)


def created_paths(taxonomy: dict[str, object]) -> list[str]:
    created = ["index.md", "log.md", ".mina-wiki", ".mina-wiki/taxonomy.json"]
    for relative_dir in taxonomy_directory_paths(taxonomy):
        created.append(relative_dir)
        created.append(f"{relative_dir}/index.md")
    return created


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        errors = [error for error in errors if "Wiki directory does not exist" not in error]
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        taxonomy = resolve_taxonomy(paths)
        ensure_wiki_structure(paths.wiki_dir, taxonomy)
        print(
            json.dumps(
                {
                    "ok": True,
                    "wiki_dir": str(paths.wiki_dir),
                    "created": created_paths(taxonomy),
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
