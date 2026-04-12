#!/usr/bin/env python3
"""Initialize git tracking for WIKI_DIR."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from wiki_common import ConfigError, is_git_repo, resolve_paths, validate_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--initial-commit",
        action="store_true",
        help="Create the first commit after initializing the wiki repository.",
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
            "user.name=Steven Wiki Skill",
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


def snapshot(wiki_dir: str) -> dict[str, object]:
    try:
        branch = run_git(wiki_dir, "rev-parse", "--abbrev-ref", "HEAD")
    except subprocess.CalledProcessError:
        branch = run_git(wiki_dir, "symbolic-ref", "--short", "HEAD")
    try:
        head = run_git(wiki_dir, "rev-parse", "HEAD")
        short_head = head[:7]
        has_commits = True
    except subprocess.CalledProcessError:
        head = None
        short_head = "unborn"
        has_commits = False
    status_short = run_git(wiki_dir, "status", "--short")
    return {
        "branch": branch,
        "head": head,
        "short_head": short_head,
        "has_commits": has_commits,
        "dirty": bool(status_short),
        "status_short": status_short.splitlines(),
    }


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
        if not is_git_repo(paths.wiki_dir):
            run_git(str(paths.wiki_dir), "init")
            created_repo = True

        has_commits = True
        try:
            run_git(str(paths.wiki_dir), "rev-parse", "HEAD")
        except subprocess.CalledProcessError:
            has_commits = False

        if args.initial_commit and not has_commits:
            run_git(str(paths.wiki_dir), "add", ".")
            run_git_commit(str(paths.wiki_dir), "Initialize wiki history")
            created_commit = True

        payload = {
            "ok": True,
            "wiki_dir": str(paths.wiki_dir),
            "created_repo": created_repo,
            "created_initial_commit": created_commit,
            "git": snapshot(str(paths.wiki_dir)),
        }
        print(json.dumps(payload, indent=2))
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
