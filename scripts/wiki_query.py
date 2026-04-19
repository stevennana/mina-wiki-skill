#!/usr/bin/env python3
"""Query wiki pages and optionally save the answer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from wiki_common import (
    ConfigError,
    append_log_entry,
    ensure_wiki_structure,
    extract_summary,
    extract_wiki_links,
    iter_wiki_pages,
    now_iso_date,
    read_wiki_page,
    resolve_paths,
    resolve_taxonomy,
    slugify,
    tokenize,
    validate_paths,
    wiki_page_ref,
    write_wiki_page,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="Question to answer from the wiki.")
    parser.add_argument("--save-to", help="Optional analysis slug or path under analyses/.")
    return parser.parse_args()


def score_page(question_tokens: list[str], title: str, body: str, ref: str = "") -> int:
    title_tokens = set(tokenize(title))
    body_tokens = set(tokenize(body))
    ref_tokens = set(tokenize(ref.replace("/", " ")))
    normalized_title = title.lower()
    normalized_body = body.lower()
    phrase = " ".join(question_tokens)
    score = 0
    for token in question_tokens:
        if token in title_tokens:
            score += 3
        if token in ref_tokens:
            score += 2
        if token in body_tokens:
            score += 1
    if phrase and phrase in normalized_title:
        score += 6
    elif phrase and phrase in normalized_body:
        score += 3
    if ref and not is_index_ref(ref):
        score += 1
    return score


def is_index_ref(ref: str) -> bool:
    return ref == "index" or ref.endswith("/index")


def resolve_ref(wiki_dir: Path, ref: str) -> Path | None:
    candidate = wiki_dir / f"{ref}.md"
    return candidate if candidate.exists() else None


def answer_from_scored(question: str, scored: list[tuple[int, Path, str]], wiki_dir: Path) -> tuple[str, list[str]]:
    ranked = sorted(
        scored,
        key=lambda item: (
            is_index_ref(wiki_page_ref(item[1], wiki_dir)),
            -item[0],
            str(item[1]),
        ),
    )
    top = ranked[:3]
    if not top:
        return "No relevant wiki pages were found for this question.", []

    lines = [f"Answer to: {question}", ""]
    citations: list[str] = []
    for _score, page, title in top:
        _metadata, body = read_wiki_page(page)
        summary = extract_summary(body) or "No summary available."
        page_ref = wiki_page_ref(page, wiki_dir)
        citations.append(page_ref)
        lines.append(f"- {title}: {summary} ([[{page_ref}]])")
    return "\n".join(lines), citations


def answer_confident(citations: list[str], scored: list[tuple[int, Path, str]]) -> bool:
    if not citations or not scored:
        return False
    top_score = scored[0][0]
    non_index_citations = [ref for ref in citations if not is_index_ref(ref)]
    if len(non_index_citations) >= 2:
        return True
    if non_index_citations and top_score >= 2:
        return True
    return False


def source_scored_search(question: str, wiki_dir: Path) -> list[tuple[int, Path, str]]:
    question_tokens = tokenize(question)
    scored: list[tuple[int, Path, str]] = []
    sources_root = wiki_dir / "sources"
    if not sources_root.exists():
        return scored
    for page in sorted(sources_root.rglob("*.md")):
        if page.name == "index.md":
            continue
        metadata, body = read_wiki_page(page)
        title = str(metadata.get("title") or page.stem)
        raw_score = score_page(question_tokens, title, body, wiki_page_ref(page, wiki_dir))
        if raw_score <= 0:
            continue
        scored.append((max(1, raw_score - 2), page, title))
    scored.sort(key=lambda item: (-item[0], str(item[1])))
    return scored


def walk_index_first(
    question: str,
    wiki_dir: Path,
    *,
    include_sources: bool,
    include_legacy: bool,
    max_depth: int = 4,
    branch_limit: int = 12,
) -> dict[str, object]:
    question_tokens = tokenize(question)
    root = wiki_dir / "index.md"
    if not root.exists():
        return {"answer": "No relevant wiki pages were found for this question.", "citations": [], "metrics": {}, "scored": []}

    visited: dict[str, tuple[int, Path, str]] = {}
    pages_by_depth: dict[int, list[Path]] = defaultdict(list)
    seed_pages: list[Path] = [root]
    for page in sorted(wiki_dir.rglob("index.md")):
        ref = wiki_page_ref(page, wiki_dir)
        if ref == "sources/index" and not include_sources:
            continue
        if ref.startswith("legacy/") and not include_legacy:
            continue
        if page not in seed_pages:
            seed_pages.append(page)
    pages_by_depth[0] = seed_pages

    def allowed(ref: str) -> bool:
        if ref.startswith("sources/") and not include_sources:
            return False
        if ref.startswith("legacy/") and not include_legacy:
            return False
        return True

    for depth in range(max_depth + 1):
        current = pages_by_depth.get(depth, [])
        if not current:
            continue
        next_candidates: list[tuple[int, Path]] = []
        for page in current:
            ref = wiki_page_ref(page, wiki_dir)
            if ref in visited:
                continue
            metadata, body = read_wiki_page(page)
            title = str(metadata.get("title") or page.stem)
            score = score_page(question_tokens, title, body, ref)
            visited[ref] = (score, page, title)
            if depth == max_depth:
                continue
            for link in extract_wiki_links(body):
                if not allowed(link):
                    continue
                linked_page = resolve_ref(wiki_dir, link)
                if linked_page is None:
                    continue
                link_meta, link_body = read_wiki_page(linked_page)
                link_title = str(link_meta.get("title") or linked_page.stem)
                preview = extract_summary(link_body) or link_body[:400]
                link_ref = wiki_page_ref(linked_page, wiki_dir)
                link_score = score_page(question_tokens, link_title, preview, link_ref)
                if link_score > 0 or (linked_page.name == "index.md" and not link.startswith("sources/")):
                    next_candidates.append((link_score, linked_page))
        if next_candidates:
            next_candidates.sort(key=lambda item: (-item[0], str(item[1])))
            deduped: list[Path] = []
            seen_paths: set[Path] = set()
            for _score, candidate in next_candidates:
                if candidate in seen_paths:
                    continue
                deduped.append(candidate)
                seen_paths.add(candidate)
                if len(deduped) >= branch_limit:
                    break
            pages_by_depth[depth + 1] = deduped

    scored = sorted(visited.values(), key=lambda item: (-item[0], str(item[1])))
    answer, citations = answer_from_scored(question, scored, wiki_dir)
    metrics = {
        "mode": "index_first",
        "visited_pages": len(visited),
        "visited_refs": list(visited.keys()),
        "include_sources": include_sources,
        "include_legacy": include_legacy,
        "top_score": scored[0][0] if scored else 0,
        "matched_pages": len(scored),
    }
    return {"answer": answer, "citations": citations, "metrics": metrics, "scored": scored}


def build_answer(question: str, wiki_dir: Path) -> tuple[str, list[str], dict[str, object]]:
    preferred = walk_index_first(question, wiki_dir, include_sources=False, include_legacy=False)
    preferred_meta = {
        "mode": "index_first",
        "used_sources_fallback": False,
        "matched_pages": preferred["metrics"].get("matched_pages", 0),
        "top_score": preferred["metrics"].get("top_score", 0),
    }
    if answer_confident(preferred["citations"], preferred["scored"]):
        return preferred["answer"], preferred["citations"], preferred_meta

    source_scored = source_scored_search(question, wiki_dir)
    if source_scored:
        answer, citations = answer_from_scored(question, source_scored, wiki_dir)
        return answer, citations, {
            "mode": "sources_fallback",
            "used_sources_fallback": True,
            "matched_pages": len(source_scored),
            "top_score": source_scored[0][0] if source_scored else 0,
        }

    question_tokens = tokenize(question)
    scored: list[tuple[int, Path, str]] = []
    for page in iter_wiki_pages(wiki_dir):
        page_ref = wiki_page_ref(page, wiki_dir)
        if page_ref.startswith("legacy/"):
            continue
        metadata, body = read_wiki_page(page)
        title = str(metadata.get("title") or page.stem)
        score = score_page(question_tokens, title, body, page_ref)
        if score > 0:
            scored.append((score, page, title))
    scored.sort(key=lambda item: (-item[0], str(item[1])))
    answer, citations = answer_from_scored(question, scored, wiki_dir)
    return answer, citations, {
        "mode": "fallback_full_scan",
        "used_sources_fallback": False,
        "matched_pages": len(scored),
        "top_score": scored[0][0] if scored else 0,
    }


def save_answer(paths, save_to: str, answer: str, citations: list[str], note: str) -> str:
    target = Path(save_to)
    slug = slugify(target.stem if target.suffix == ".md" else target.name)
    analysis_path = paths.wiki_dir / "analyses" / f"{slug}.md"
    metadata = {
        "type": "analysis",
        "title": slug.replace("-", " ").title(),
        "last_reviewed": now_iso_date(),
        "sources": citations,
    }
    body = "## Summary\n\n" + answer + "\n\n## Links\n\n" + "\n".join(f"- [[{citation}]]" for citation in citations)
    write_wiki_page(analysis_path, metadata, body)
    subprocess.run(
        ["python3", str(Path(__file__).resolve().parent / "wiki_index.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    append_log_entry(paths.wiki_dir, "query", [str(analysis_path.relative_to(paths.wiki_dir))], note=note)
    return str(analysis_path)


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        taxonomy = resolve_taxonomy(paths)
        ensure_wiki_structure(paths.wiki_dir, taxonomy)
        answer, citations, query_meta = build_answer(args.question, paths.wiki_dir)
        saved_path = save_answer(paths, args.save_to, answer, citations, args.question) if args.save_to else None
        print(json.dumps({"ok": True, "answer": answer, "citations": citations, "saved_path": saved_path, **query_meta}, indent=2))
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
