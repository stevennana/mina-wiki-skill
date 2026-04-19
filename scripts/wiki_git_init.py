#!/usr/bin/env python3
"""Inspect project-level git tracking for WIKI_DIR."""

from __future__ import annotations

import json
import sys

from wiki_common import ConfigError, git_toplevel, resolve_paths, safe_relative_to, validate_paths


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        repo_root = git_toplevel(paths.wiki_dir)
        if repo_root is None:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": (
                            "WIKI_DIR is not inside a git repository. "
                            "Use a project-level git repo for wiki history; do not initialize a nested wiki repo."
                        ),
                    },
                    indent=2,
                )
            )
            return 1

        relative_wiki_dir = str(safe_relative_to(paths.wiki_dir, repo_root))
        print(
            json.dumps(
                {
                    "ok": True,
                    "wiki_dir": str(paths.wiki_dir),
                    "repo_root": str(repo_root),
                    "wiki_dir_relative_to_repo": relative_wiki_dir,
                    "uses_project_level_git": True,
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
