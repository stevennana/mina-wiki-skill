#!/usr/bin/env python3
"""Query wiki pages and optionally save the answer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from wiki_common import (
    ConfigError,
    append_log_entry,
    ensure_wiki_structure,
    extract_summary,
    iter_wiki_pages,
    now_iso_date,
    read_wiki_page,
    resolve_paths,
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


def score_page(question_tokens: list[str], title: str, body: str, ref: str) -> int:
    haystack = set(tokenize(f"{title}\n{body}\n{ref}"))
    score = sum(1 for token in question_tokens if token in haystack)
    if ref == "index":
        score += 3
    elif ref.endswith("/index"):
        score += 2
    return score


def build_answer(question: str, wiki_dir: Path) -> tuple[str, list[str]]:
    question_tokens = tokenize(question)
    scored: list[tuple[int, Path, str, str]] = []
    for page in iter_wiki_pages(wiki_dir):
        metadata, body = read_wiki_page(page)
        title = str(metadata.get("title") or page.stem)
        ref = wiki_page_ref(page, wiki_dir)
        score = score_page(question_tokens, title, body, ref)
        if score > 0:
            scored.append((score, page, title, ref))
    scored.sort(key=lambda item: (-item[0], str(item[1])))
    top = scored[:4]
    if not top:
        return "No relevant wiki pages were found for this question.", []

    lines = [f"Answer to: {question}", ""]
    citations: list[str] = []
    for _score, page, title, ref in top:
        _metadata, body = read_wiki_page(page)
        summary = extract_summary(body) or "No summary available."
        citations.append(ref)
        lines.append(f"- {title}: {summary} ([[{ref}]])")
    return "\n".join(lines), citations


def save_answer(paths, save_to: str, answer: str, citations: list[str]) -> str:
    target = Path(save_to)
    if target.suffix == ".md":
        slug = slugify(target.stem)
    else:
        slug = slugify(target.name)
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
    append_log_entry(paths.wiki_dir, "query", [str(analysis_path.relative_to(paths.wiki_dir))], note=answer.splitlines()[0])
    return str(analysis_path)


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        ensure_wiki_structure(paths.wiki_dir)
        answer, citations = build_answer(args.question, paths.wiki_dir)
        saved_path = save_answer(paths, args.save_to, answer, citations) if args.save_to else None
        print(json.dumps({"ok": True, "answer": answer, "citations": citations, "saved_path": saved_path}, indent=2))
        return 0
    except (ConfigError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
