# Project Integration

This repository is meant to be adopted into another project, not run in isolation forever. The receiving project's local agent docs should make the wiki workflow explicit so every future Codex or Claude session uses the same memory model.

## Inject Into `AGENTS.md`

Recommended section title:

`## Wiki Workflow`

Recommended guidance:

- This project uses `mina-wiki-skill` for long-lived markdown knowledge management across Codex and Claude sessions.
- `WIKI_DIR` is the maintained project memory and should be consulted before re-deriving answers from raw material.
- `WIKI_RAW_DIR` is ingestion input and should not be treated as the default reading surface.
- Query the wiki with an `index-first` approach: root `index.md` -> section indexes -> leaf pages.
- Use `sources/` only as fallback when maintained pages are insufficient.
- Keep taxonomy project-local via `.mina-wiki.json` or `WIKI_DIR/.mina-wiki/taxonomy.json`; do not hardcode domain taxonomy into shared helpers.
- Raw may use its own dedicated git repository.
- The wiki must not create a nested git repository; commit wiki changes through the parent project repository that contains `WIKI_DIR`.
- After meaningful wiki changes, rebuild indexes and run lint / quality / principle checks.

Minimum command block:

```text
python3 scripts/wiki_sync_status.py
python3 scripts/wiki_sync.py --update-sync-marker
python3 scripts/wiki_index.py
python3 scripts/wiki_quality_audit.py
python3 scripts/wiki_lint.py
python3 scripts/wiki_enforce_principles.py
```

## Inject Into `CLAUDE.md`

Recommended section title:

`## Wiki Memory Rules`

Recommended guidance:

- Use the maintained wiki as the first source of truth for project questions.
- Start from `index.md`, then follow section indexes and leaf pages before reading raw material.
- Treat `sources/` as fallback evidence, not the primary surface.
- When raw changed, check sync status first and ask before running a full wiki sync.
- When updating the wiki, preserve stable structure, avoid placeholder text, and prefer stronger maintained pages over raw mirrors.
- Keep wiki history inside the parent project repository. Do not run `git init` inside `WIKI_DIR`.
- If the project defines a taxonomy, keep it in config, not in shared skill code.

## Shared Intent

If both `AGENTS.md` and `CLAUDE.md` exist in the receiving project, they should agree on these points:

- the wiki is the default project memory
- raw is ingestion input
- retrieval is `index-first`
- `sources/` is fallback-only
- wiki history uses the parent project repo
- taxonomy is configured locally

## Suggested Project Setup Notes

- Put `WIKI_RAW_DIR` and `WIKI_DIR` in project-local `.mina-wiki.json` when possible.
- Keep `WIKI_DIR` inside the project repository if you want wiki changes committed with normal project history.
- Use `python3 scripts/wiki_benchmark.py` with project-specific question sets when tuning retrieval quality.

## Anti-Patterns To Call Out

- Raw-first browsing for ordinary project questions
- Creating nested wiki git repositories
- Allowing `sources/` to become the primary answer path
- Extending flat legacy namespaces instead of migrating them
- Skipping lint / audit / enforcement after large wiki edits
