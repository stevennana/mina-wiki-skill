#!/usr/bin/env python3
"""Slash-command catalog for mina-wiki-skill."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    name: str
    summary: str
    usage: str
    behavior: tuple[str, ...]
    examples: tuple[str, ...]
    safety_notes: tuple[str, ...] = ()


COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand(
        name="wiki-status",
        summary="Report whether the shared wiki is behind raw.",
        usage="/wiki-status",
        behavior=(
            "Run `python3 scripts/check_paths.py`.",
            "Run `python3 scripts/wiki_sync_status.py`.",
            "Summarize `needs_sync`, raw branch/commit, changed files, and sync reasons.",
        ),
        examples=("/wiki-status",),
    ),
    SlashCommand(
        name="wiki-sync",
        summary="Sync wiki pages from raw changes after user approval.",
        usage="/wiki-sync [optional raw path]",
        behavior=(
            "Run sync-status first.",
            "If raw has changed, ask the user for approval before editing wiki pages.",
            "After approval, run `python3 scripts/wiki_sync.py --update-sync-marker` for full-directory sync or sync the requested raw path.",
            "Update affected pages, rebuild root and section indexes, append to `log.md`, and refresh sync metadata.",
        ),
        examples=("/wiki-sync", "/wiki-sync docs/example-source.md"),
        safety_notes=("Never edit files in `WIKI_RAW_DIR`.",),
    ),
    SlashCommand(
        name="wiki-add-source",
        summary="Ingest a specific raw source into the shared wiki.",
        usage="/wiki-add-source <raw-path>",
        behavior=(
            "Read the raw source relative to `WIKI_RAW_DIR`.",
            "Create or update a page in `sources/`.",
            "Update the maintained topic page using configured taxonomy or fallback destination, rebuild the relevant indexes, and append to `log.md`.",
        ),
        examples=("/wiki-add-source docs/example-source.md",),
    ),
    SlashCommand(
        name="wiki-update-page",
        summary="Update an existing wiki page from raw or session-derived knowledge.",
        usage="/wiki-update-page <wiki-path> [instruction]",
        behavior=(
            "Inspect the existing page and gather relevant raw/wiki context.",
            "Revise the target page without changing raw files.",
            "Repair nearby links when the update changes references and append to `log.md`.",
        ),
        examples=(
            "/wiki-update-page topics/example-topic.md refine the explanation and add source coverage",
        ),
    ),
    SlashCommand(
        name="wiki-delete-page",
        summary="Delete or archive a wiki page safely.",
        usage="/wiki-delete-page <wiki-path> [replacement-page]",
        behavior=(
            "Require explicit user confirmation before any destructive action.",
            "Prefer archive or merge semantics over hard delete when useful history exists.",
            "Remove or repair obvious inbound references and append a delete/archive entry to `log.md`.",
        ),
        examples=("/wiki-delete-page analyses/old-comparison.md", "/wiki-delete-page legacy/flat/concepts/old-topic.md"),
        safety_notes=("Always ask for confirmation before deleting or archiving a page.",),
    ),
    SlashCommand(
        name="wiki-query",
        summary="Answer a question from wiki pages and optionally file the result back.",
        usage="/wiki-query <question>",
        behavior=(
            "Read `index.md` first, then only the relevant pages.",
            "Answer with citations to wiki pages.",
            "If the user asks to save the result, write it to `analyses/` and log the operation.",
        ),
        examples=("/wiki-query What does the example topic cover in this system?",),
    ),
    SlashCommand(
        name="wiki-lint",
        summary="Health-check the wiki for stale content and structural issues.",
        usage="/wiki-lint",
        behavior=(
            "Identify stale pages after raw changes.",
            "Find orphan pages, weak cross-links, contradiction candidates, and missing summaries.",
        ),
        examples=("/wiki-lint",),
    ),
    SlashCommand(
        name="wiki-log",
        summary="Append a structured operation entry to the wiki log.",
        usage="/wiki-log <operation> [touched pages...]",
        behavior=(
            "Use `python3 scripts/log_operation.py`.",
            "Include operation name and touched pages.",
            "Update sync metadata only when the wiki reflects current raw state.",
        ),
        examples=("/wiki-log ingest sources/example-source.md topics/example-topic.md",),
    ),
)
