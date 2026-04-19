#!/usr/bin/env python3
"""Provide session-start guidance for raw/wiki sync decisions."""

from __future__ import annotations

import json
import sys

from wiki_common import ConfigError, compute_sync_status, resolve_paths, resolve_taxonomy, validate_paths


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        status = compute_sync_status(paths)
        taxonomy = resolve_taxonomy(paths)
        recommended_steps = ["python3 scripts/wiki_sync_status.py"]
        if status["needs_sync"]:
            recommended_steps.append("python3 scripts/wiki_sync.py --update-sync-marker")
        recommended_steps.extend(
            [
                "python3 scripts/wiki_index.py",
                "python3 scripts/wiki_quality_audit.py",
                "python3 scripts/wiki_lint.py",
                "python3 scripts/wiki_enforce_principles.py",
            ]
        )
        payload = {
            "ok": True,
            "needs_sync": status["needs_sync"],
            "should_prompt_user": status["needs_sync"],
            "reasons": status["reasons"],
            "changed_raw_files": status["raw"]["changed_files"],
            "raw_head": status["raw"]["short_head"],
            "raw_has_commits": status["raw"]["has_commits"],
            "baseline_commit_recommended": status["baseline_commit_recommended"],
            "follow_up_actions": status["follow_up_actions"],
            "sync_metadata_path": status["sync_metadata_path"],
            "taxonomy_roots": taxonomy["root_sections"],
            "default_destination": taxonomy["default_destination"],
            "recommended_steps": recommended_steps,
        }
        print(json.dumps(payload, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
