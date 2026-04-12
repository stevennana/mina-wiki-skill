#!/usr/bin/env python3
"""Initialize git tracking for WIKI_RAW_DIR."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from wiki_common import ConfigError, git_snapshot, is_git_repo, resolve_paths, validate_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--initial-commit",
        action="store_true",
        help="Create the first baseline commit after initializing the repository.",
    )
    return parser.parse_args()


def run_git(raw_dir: str, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=raw_dir,
        check=True,
        capture_output=True,
        text=True,
    )


def run_git_commit(raw_dir: str, message: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Steven Wiki Skill",
            "-c",
            "user.email=steven-wiki-skill@local",
            "commit",
            "-m",
            message,
        ],
        cwd=raw_dir,
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        created_repo = False
        created_commit = False
        if not is_git_repo(paths.raw_dir):
            run_git(str(paths.raw_dir), "init")
            created_repo = True

        snapshot = git_snapshot(paths.raw_dir)
        if args.initial_commit and not snapshot["has_commits"]:
            run_git(str(paths.raw_dir), "add", ".")
            run_git_commit(str(paths.raw_dir), "Initial raw baseline")
            created_commit = True
            snapshot = git_snapshot(paths.raw_dir)

        payload = {
            "ok": True,
            "raw_dir": str(paths.raw_dir),
            "created_repo": created_repo,
            "created_initial_commit": created_commit,
            "git": snapshot,
        }
        print(json.dumps(payload, indent=2))
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
