#!/usr/bin/env python3
"""Commit a meaningful wiki batch in WIKI_DIR."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from wiki_common import ConfigError, is_git_repo, resolve_paths, validate_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", required=True, help="Commit message for the wiki batch.")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Wiki-relative files to stage. If omitted, stages all changes.",
    )
    return parser.parse_args()


def run_git(wiki_dir: str, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=wiki_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def run_git_commit(wiki_dir: str, message: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=mina-wiki-skill",
            "-c",
            "user.email=mina-wiki-skill@local",
            "commit",
            "-m",
            message,
        ],
        cwd=wiki_dir,
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
        if not is_git_repo(paths.wiki_dir):
            raise ConfigError(f"Wiki directory is not a git repository: {paths.wiki_dir}")

        if args.paths:
            run_git(str(paths.wiki_dir), "add", *args.paths)
        else:
            run_git(str(paths.wiki_dir), "add", ".")

        status_short = run_git(str(paths.wiki_dir), "status", "--short")
        if not status_short:
            print(json.dumps({"ok": True, "committed": False, "message": "No wiki changes to commit."}, indent=2))
            return 0

        run_git_commit(str(paths.wiki_dir), args.message)
        head = run_git(str(paths.wiki_dir), "rev-parse", "HEAD")
        print(
            json.dumps(
                {"ok": True, "committed": True, "message": args.message, "head": head, "short_head": head[:7]},
                indent=2,
            )
        )
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
