#!/usr/bin/env python3
"""Benchmark wiki answer efficiency using an external question set."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

from wiki_common import ConfigError, read_wiki_page, resolve_paths, validate_paths
from wiki_query import build_answer, walk_index_first


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True, help="Path to JSON or CSV question set.")
    parser.add_argument("--output-json", required=True, help="Path to write structured benchmark results.")
    parser.add_argument("--output-md", help="Optional path to write a markdown summary.")
    parser.add_argument("--compare-json", help="Optional prior benchmark JSON to compare against.")
    parser.add_argument("--write-baseline", action="store_true", help="Write the current run as the default benchmark baseline.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit non-zero when comparison deltas regress.")
    parser.add_argument("--max-elapsed-regression-ms", type=float, default=0.0, help="Allowed avg elapsed regression in ms.")
    parser.add_argument(
        "--max-context-regression-tokens",
        type=float,
        default=0.0,
        help="Allowed avg matched-context regression in estimated tokens.",
    )
    parser.add_argument(
        "--max-fallback-regression",
        type=int,
        default=0,
        help="Allowed increase in sources fallback count compared to the baseline.",
    )
    return parser.parse_args()


def load_questions(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ConfigError("Question set JSON must be a list of question objects.")
        return [{str(k): str(v) for k, v in item.items()} for item in payload]
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [{str(k): str(v) for k, v in row.items()} for row in csv.DictReader(handle)]
    raise ConfigError("Question set must be JSON or CSV.")


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def page_token_cost(wiki_dir: Path, ref: str) -> int:
    page = wiki_dir / f"{ref}.md"
    if not page.exists():
        return 0
    metadata, body = read_wiki_page(page)
    title = str(metadata.get("title") or page.stem)
    return estimate_tokens(title + "\n" + body)


def benchmark_question(wiki_dir: Path, question_row: dict[str, str]) -> dict[str, object]:
    question = question_row.get("question", "").strip()
    if not question:
        raise ConfigError("Each benchmark question row must include a non-empty `question` field.")
    started = time.perf_counter()
    answer, citations, query_meta = build_answer(question, wiki_dir)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    cited_token_cost = sum(page_token_cost(wiki_dir, ref) for ref in citations)
    matched_pages = len(citations)
    matched_token_cost = cited_token_cost
    if query_meta["mode"] == "index_first":
        index_result = walk_index_first(question, wiki_dir, include_sources=False, include_legacy=False)
        matched_pages = len(index_result["scored"])
        matched_token_cost = sum(page_token_cost(wiki_dir, ref) for ref in index_result["metrics"]["visited_refs"])
    return {
        **question_row,
        "mode": query_meta["mode"],
        "used_sources_fallback": query_meta["used_sources_fallback"],
        "elapsed_ms": elapsed_ms,
        "answer_tokens_est": estimate_tokens(answer),
        "cited_context_tokens_est": cited_token_cost,
        "matched_context_tokens_est": matched_token_cost,
        "matched_pages": matched_pages,
        "cited_pages": len(citations),
        "top_score": query_meta["top_score"],
        "answer": answer,
        "citations": citations,
    }


def summarize(results: list[dict[str, object]]) -> dict[str, object]:
    count = len(results)
    return {
        "question_count": count,
        "avg_elapsed_ms": round(sum(r["elapsed_ms"] for r in results) / count, 3) if count else 0,
        "median_elapsed_ms": sorted(r["elapsed_ms"] for r in results)[count // 2] if count else 0,
        "avg_answer_tokens_est": round(sum(r["answer_tokens_est"] for r in results) / count, 2) if count else 0,
        "avg_cited_context_tokens_est": round(sum(r["cited_context_tokens_est"] for r in results) / count, 2) if count else 0,
        "avg_matched_context_tokens_est": round(sum(r["matched_context_tokens_est"] for r in results) / count, 2) if count else 0,
        "avg_matched_pages": round(sum(r["matched_pages"] for r in results) / count, 2) if count else 0,
        "sources_fallback_count": sum(1 for r in results if r["used_sources_fallback"]),
        "index_first_count": sum(1 for r in results if r["mode"] == "index_first"),
    }


def render_markdown(results: list[dict[str, object]], summary: dict[str, object]) -> str:
    lines = [
        "# Wiki Benchmark",
        "",
        "## Summary",
        "",
        f"- Question count: {summary['question_count']}",
        f"- Avg elapsed ms: {summary['avg_elapsed_ms']}",
        f"- Median elapsed ms: {summary['median_elapsed_ms']}",
        f"- Avg cited context tokens est: {summary['avg_cited_context_tokens_est']}",
        f"- Avg matched context tokens est: {summary['avg_matched_context_tokens_est']}",
        f"- Sources fallback count: {summary['sources_fallback_count']}",
        "",
        "## Results",
        "",
        "| ID | Mode | Elapsed ms | Matched pages | Fallback |",
        "|---|---|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            f"| {row.get('id', '')} | {row['mode']} | {row['elapsed_ms']} | {row['matched_pages']} | {row['used_sources_fallback']} |"
        )
    return "\n".join(lines) + "\n"


def build_comparison(current: dict[str, object], previous: dict[str, object]) -> dict[str, object]:
    prev_summary = previous.get("summary", {})
    return {
        "avg_elapsed_ms_delta": round(current["avg_elapsed_ms"] - prev_summary.get("avg_elapsed_ms", 0), 3),
        "avg_cited_context_tokens_est_delta": round(
            current["avg_cited_context_tokens_est"] - prev_summary.get("avg_cited_context_tokens_est", 0), 2
        ),
        "avg_matched_context_tokens_est_delta": round(
            current["avg_matched_context_tokens_est"] - prev_summary.get("avg_matched_context_tokens_est", 0), 2
        ),
        "sources_fallback_count_delta": current["sources_fallback_count"] - prev_summary.get("sources_fallback_count", 0),
    }


def is_regression(comparison: dict[str, object], args: argparse.Namespace) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if comparison["avg_elapsed_ms_delta"] > args.max_elapsed_regression_ms:
        reasons.append("avg_elapsed_ms_regressed")
    if comparison["avg_matched_context_tokens_est_delta"] > args.max_context_regression_tokens:
        reasons.append("avg_matched_context_tokens_est_regressed")
    if comparison["sources_fallback_count_delta"] > args.max_fallback_regression:
        reasons.append("sources_fallback_count_regressed")
    return bool(reasons), reasons


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_paths()
        errors = validate_paths(paths)
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        questions = load_questions(Path(args.questions).resolve())
        results = [benchmark_question(paths.wiki_dir, question_row) for question_row in questions]
        summary = summarize(results)
        baseline_path = paths.wiki_dir / ".mina-wiki" / "benchmarks" / "baseline.json"
        comparison = None
        regression = None
        compare_path = Path(args.compare_json).resolve() if args.compare_json else (baseline_path if baseline_path.exists() else None)
        if compare_path:
            previous = json.loads(compare_path.read_text(encoding="utf-8"))
            comparison = build_comparison(summary, previous)
            if args.fail_on_regression:
                failed, reasons = is_regression(comparison, args)
                regression = {"failed": failed, "reasons": reasons}
        output_json = Path(args.output_json).resolve()
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(
                {"results": results, "summary": summary, "comparison": comparison, "regression": regression},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        if args.write_baseline:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(
                json.dumps({"results": results, "summary": summary}, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        output_md = None
        if args.output_md:
            output_md = Path(args.output_md).resolve()
            output_md.parent.mkdir(parents=True, exist_ok=True)
            output_md.write_text(render_markdown(results, summary), encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "output_json": str(output_json),
                    "output_md": str(output_md) if output_md else None,
                    "comparison_included": comparison is not None,
                    "regression": regression,
                    "baseline_path": str(baseline_path) if args.write_baseline or baseline_path.exists() else None,
                },
                indent=2,
            )
        )
        return 2 if regression and regression["failed"] else 0
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
