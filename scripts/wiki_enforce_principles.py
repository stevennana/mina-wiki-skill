#!/usr/bin/env python3
"""Check generic wiki structure principles across maintained pages."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    extract_summary,
    extract_wiki_links,
    is_index_ref,
    is_legacy_ref,
    is_source_ref,
    iter_wiki_pages,
    read_wiki_page,
    resolve_paths,
    validate_paths,
    wiki_page_ref,
    write_wiki_page,
)


PLACEHOLDER_TEXT = "Auto-maintained"


def parse_args() -> tuple[bool]:
    return ("--apply" in sys.argv[1:],)


def fix_body(ref: str, metadata: dict[str, object], body: str) -> str:
    title = str(metadata.get("title") or Path(ref).stem.replace("-", " ").title())
    lines = []
    for line in body.splitlines():
        if "[[legacy/" in line and not is_legacy_ref(ref):
            continue
        lines.append(line)
    updated = "\n".join(lines)
    if PLACEHOLDER_TEXT in updated:
        updated = updated.replace(PLACEHOLDER_TEXT, "").replace("  ", " ")
    if not extract_summary(updated):
        updated = f"## Summary\n\n{title} is part of the maintained wiki.\n\n" + updated.strip()
    if metadata.get("sources") and "## Source Coverage" not in updated:
        source_items = metadata["sources"]
        if isinstance(source_items, str):
            source_items = [source_items]
        coverage = "\n".join(f"- [[{item}]]" for item in source_items)
        updated = updated.rstrip() + "\n\n## Source Coverage\n\n" + coverage + "\n"
    return updated.strip() + "\n"


def main() -> int:
    try:
        apply_fixes = parse_args()[0]
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        violations: list[dict[str, str]] = []
        auto_fixable: list[dict[str, str]] = []
        manual_review: list[dict[str, str]] = []
        fixed_pages: list[str] = []
        refs = {wiki_page_ref(page, paths.wiki_dir): page for page in iter_wiki_pages(paths.wiki_dir)}
        inbound: dict[str, int] = {ref: 0 for ref in refs}

        for ref, page in refs.items():
            _metadata, body = read_wiki_page(page)
            for link in extract_wiki_links(body):
                if link in inbound:
                    inbound[link] += 1

        for ref, page in refs.items():
            metadata, body = read_wiki_page(page)
            if is_source_ref(ref):
                continue

            if PLACEHOLDER_TEXT in body:
                auto_fixable.append({"ref": ref, "issue": "placeholder_text"})
            if not extract_summary(body):
                auto_fixable.append({"ref": ref, "issue": "missing_summary"})

            if is_index_ref(ref):
                links = [link for link in extract_wiki_links(body) if not is_source_ref(link) and not is_legacy_ref(link)]
                if not links:
                    violations.append({"ref": ref, "issue": "empty_index"})
                source_links = [link for link in extract_wiki_links(body) if is_source_ref(link)]
                if source_links and len(source_links) == len(extract_wiki_links(body)):
                    manual_review.append({"ref": ref, "issue": "index_depends_only_on_sources"})
                if apply_fixes:
                    updated = fix_body(ref, metadata, body)
                    if updated != body:
                        write_wiki_page(page, metadata, updated)
                        fixed_pages.append(ref)
                continue

            if is_legacy_ref(ref):
                if inbound.get(ref, 0) > 0:
                    manual_review.append({"ref": ref, "issue": "legacy_referenced_from_active_surface"})
                continue

            if inbound.get(ref, 0) == 0:
                violations.append({"ref": ref, "issue": "orphan_leaf"})
            parent_index_ref = f"{Path(ref).parent.as_posix()}/index" if "/" in ref else "index"
            if parent_index_ref not in refs:
                manual_review.append({"ref": ref, "issue": "missing_parent_index"})
            if "## Source Coverage" not in body and metadata.get("sources"):
                auto_fixable.append({"ref": ref, "issue": "missing_source_coverage_section"})

            if apply_fixes:
                updated = fix_body(ref, metadata, body)
                if updated != body:
                    write_wiki_page(page, metadata, updated)
                    fixed_pages.append(ref)

        payload = {
            "ok": True,
            "violations": violations,
            "auto_fixable": auto_fixable,
            "manual_review": manual_review,
            "fixed_pages": fixed_pages,
            "summary": {
                "violations": len(violations),
                "auto_fixable": len(auto_fixable),
                "manual_review": len(manual_review),
                "fixed_pages": len(fixed_pages),
            },
        }
        print(json.dumps(payload, indent=2))
        return 0 if not violations and not manual_review else 2
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
