---
name: mina-wiki-skill
description: Maintain a shared markdown wiki from raw source directories and session-derived knowledge. Use when an adopted LLM CLI project should detect raw updates, sync wiki pages, answer from the wiki, or lint a persistent knowledge base backed by WIKI_RAW_DIR and WIKI_DIR.
---

This skill turns an adopted LLM CLI session into a disciplined maintainer of a general-purpose markdown wiki.

The wiki is the primary knowledge source. `WIKI_RAW_DIR` is ingestion input, not the normal browsing surface. Helper scripts bootstrap, sync, index, lint, and log the wiki, but the LLM using this skill still owns the editorial work.

## Default Structure

The maintained wiki always includes:

- root `index.md` as the navigation entrypoint
- `sources/` for raw-source summaries
- `analyses/` for synthesis, troubleshooting, and filed answers
- `legacy/` for archived material
- project-defined maintained sections and nested indexes

Section names and hierarchy are not hardcoded to a specific domain. They come from project config or wiki-local taxonomy metadata when available. If no taxonomy is configured, the skill falls back to a minimal generic structure with `topics/`, `analyses/`, `sources/`, and `legacy/`.

## Required Working Loop

When the user asks for the wiki to be built, refreshed, upgraded, or maintained:

1. validate paths and sync status
2. bootstrap or sync the wiki structure
3. read raw files one by one or in tight batches
4. update `sources/` pages and the maintained topic pages
5. rebuild indexes
6. run lint, quality, and principle checks
7. fix what the checks expose
8. log the batch and update sync metadata when the wiki reflects current raw state

Do not stop after script generation or initial sync. A script-only pass is incomplete.

## Session Start

At session start:

1. run `python3 scripts/wiki_sync_status.py`
2. if `needs_sync` is `true`, tell the user raw changed and ask whether to sync now
3. if accepted, run the sync flow, inspect touched pages, improve weak summaries, rebuild indexes, append to `log.md`, and update the sync marker
4. if declined, continue but state that the wiki may lag raw

When `baseline_commit_recommended` is `true`, treat the run as initial bootstrap guidance. Finish the first useful sync, then create the first commit in `WIKI_RAW_DIR`.

Raw may use its own dedicated git repository. The wiki should not create its own nested git repository; it should live inside and commit through the parent project repository.

## Mandatory Execution Order

When maintaining the wiki:

1. `python3 scripts/check_paths.py`
2. `python3 scripts/wiki_sync_status.py`
3. if needed, `python3 scripts/wiki_sync.py --update-sync-marker`
4. if replacing generated material cleanly, `python3 scripts/wiki_sync.py --reset-generated --update-sync-marker`
5. if migrating an old flat wiki, `python3 scripts/migrate_to_hierarchical.py`
6. read raw files and editorially improve touched pages
7. `python3 scripts/wiki_index.py`
8. `python3 scripts/wiki_quality_audit.py`
9. `python3 scripts/wiki_lint.py`
10. `python3 scripts/wiki_enforce_principles.py`
11. fix what the checks expose
12. rerun the checks

## Non-Negotiable Editing Rules

- Read root `index.md` before targeted wiki work.
- Re-read every page before editing it.
- Prefer maintained topic pages over raw-source mirrors.
- Treat `sources/` as evidence summaries, not the main user-facing knowledge surface.
- Keep `last_reviewed` stable during automatic cleanup or relinking. Only update it for new pages or deliberate editorial revisions.
- Prefer one strong maintained page over many thin stubs.
- Split overgrown pages by stable topic or workflow, not chronology.
- Rewrite generated placeholders instead of preserving them.
- If a flat legacy page exists, migrate or archive it instead of extending the old namespace.

## Taxonomy Rules

- The skill is general-purpose. It must not hardcode one project's domain taxonomy as the global default.
- Project-specific hierarchy belongs in config or wiki-local taxonomy metadata.
- If taxonomy config is present, bootstrap, ingest, sync, migration, and index rebuild must all follow it.
- If taxonomy config is absent, use the minimal fallback structure rather than inventing domain-specific section names.

## Query Workflow

When the user asks a domain question:

1. read `index.md`
2. read the most relevant section indexes
3. read the relevant leaf pages
4. answer from the wiki
5. if the answer is durable, save it under `analyses/` and log it

The retrieval default is `index-first`. `sources/` is a fallback-only surface, not the first-pass browsing path.

Do not browse raw first for ordinary domain questions unless the wiki is missing or stale.

## Benchmarking

- Use `python3 scripts/wiki_benchmark.py` with an external question set when you need to measure whether the maintained hierarchy is actually helping retrieval.
- Favor benchmarks that measure `index -> section index -> leaf page` traversal rather than brute-force full-corpus scans.
- Treat a benchmark regression as a wiki structure problem unless the query implementation changed.

## Quality Bar

Reject these failure modes:

- project-specific taxonomy hardcoded into the skill itself
- raw-file mirrors without synthesis
- placeholder text such as `Auto-maintained`
- thin maintained pages with no explanation
- stale indexes after major edits
- isolated leaf pages with weak backlinks
- unnecessary metadata churn from automatic sync steps

The wiki is only healthy when maintained pages, source summaries, and indexes agree on the same configured structure.

## Project Integration

When this skill is adopted into another project, the receiving project's `AGENTS.md` or `CLAUDE.md` should establish these rules explicitly:

- The wiki is the default project memory. Raw is ingestion input, not the first-pass browsing surface.
- Query behavior is `index-first`, with `sources/` used only as fallback.
- Raw may live in its own dedicated git repository.
- The wiki must not initialize its own nested git repository.
- Wiki changes must be committed through the parent project repository that contains `WIKI_DIR`.
- Taxonomy belongs in project config or wiki-local metadata, not in the shared skill code.
- Quality checks are part of normal operation, not optional cleanup.

If the receiving project already has local operating rules, inject the wiki guidance as an additive section rather than replacing unrelated project instructions.
