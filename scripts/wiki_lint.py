#!/usr/bin/env python3
"""Lint the shared wiki for structural issues and stale content."""

from __future__ import annotations

import json
import sys

from wiki_common import (
    ConfigError,
    compute_sync_status,
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
)


def main() -> int:
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1

        pages = iter_wiki_pages(paths.wiki_dir)
        refs = {wiki_page_ref(page, paths.wiki_dir): page for page in pages}
        inbound: dict[str, int] = {ref: 0 for ref in refs}
        missing_summary: list[str] = []
        missing_frontmatter: list[str] = []
        contradiction_candidates: list[str] = []

        for ref, page in refs.items():
            metadata, body = read_wiki_page(page)
            if not metadata:
                missing_frontmatter.append(ref)
            if not extract_summary(body):
                missing_summary.append(ref)
            for link in extract_wiki_links(body):
                if link in inbound:
                    inbound[link] += 1
            lower_body = body.lower()
            if "contradict" in lower_body or "however" in lower_body or "but " in lower_body:
                contradiction_candidates.append(ref)

        orphan_pages = sorted(
            ref
            for ref, count in inbound.items()
            if count == 0 and not is_source_ref(ref) and not is_index_ref(ref) and not is_legacy_ref(ref)
        )
        underlinked_leaf_pages = sorted(
            ref
            for ref, count in inbound.items()
            if count == 0 and not is_source_ref(ref) and not is_index_ref(ref) and not ref.startswith("analyses/")
        )
        sync_status = compute_sync_status(paths)
        stale_pages = []
        if sync_status["needs_sync"]:
            for ref, page in refs.items():
                metadata, _body = read_wiki_page(page)
                if metadata.get("raw_commit") and metadata.get("raw_commit") != sync_status["raw"]["short_head"]:
                    stale_pages.append(ref)

        payload = {
            "ok": True,
            "orphan_pages": orphan_pages,
            "underlinked_leaf_pages": underlinked_leaf_pages,
            "missing_summary": sorted(missing_summary),
            "missing_frontmatter": sorted(missing_frontmatter),
            "contradiction_candidates": sorted(set(contradiction_candidates)),
            "stale_pages": sorted(stale_pages),
            "sync_needs_attention": sync_status["needs_sync"],
            "sync_reasons": sync_status["reasons"],
        }
        print(json.dumps(payload, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
