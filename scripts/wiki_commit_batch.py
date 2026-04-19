#!/usr/bin/env python3
"""Commit a meaningful wiki batch using the project-level git repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from wiki_common import ConfigError, git_toplevel, resolve_paths, safe_relative_to, validate_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", required=True, help="Commit message for the wiki batch.")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Wiki-relative files to stage. If omitted, stages the full wiki directory.",
    )
    return parser.parse_args()


def run_git(repo_root: str, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def run_git_commit(repo_root: str, message: str) -> None:
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
        cwd=repo_root,
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

        repo_root = git_toplevel(paths.wiki_dir)
        if repo_root is None:
            raise ConfigError(
                "WIKI_DIR is not inside a git repository. Commit wiki changes through the parent project git repository."
            )

        wiki_dir_relative = safe_relative_to(paths.wiki_dir, repo_root)
        if args.paths:
            stage_paths = [str((wiki_dir_relative / Path(path)).as_posix()) for path in args.paths]
        else:
            stage_paths = [str(wiki_dir_relative.as_posix())]

        run_git(str(repo_root), "add", *stage_paths)

        status_short = run_git(str(repo_root), "status", "--short")
        if not status_short:
            print(json.dumps({"ok": True, "committed": False, "message": "No wiki changes to commit."}, indent=2))
            return 0

        run_git_commit(str(repo_root), args.message)
        head = run_git(str(repo_root), "rev-parse", "HEAD")
        print(
            json.dumps(
                {
                    "ok": True,
                    "committed": True,
                    "message": args.message,
                    "head": head,
                    "short_head": head[:7],
                    "repo_root": str(repo_root),
                    "staged_paths": stage_paths,
                },
                indent=2,
            )
        )
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
