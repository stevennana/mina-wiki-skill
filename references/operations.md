# Operations

## Session Start

Run `python3 scripts/wiki_sync_status.py` first.

- If `needs_sync` is `false`, continue normally.
- If `needs_sync` is `true`, tell the user raw changed and ask whether to sync now.
- If accepted, inspect the changed raw files, update affected wiki pages, rebuild root and section indexes, append to `log.md`, and update the sync marker.
- If `baseline_commit_recommended` is `true`, treat the run as initial bootstrap. Finish the first useful wiki sync, then create the first commit in `WIKI_RAW_DIR`.
- If raw is not a git repo yet, bootstrap the wiki first, then run `python3 scripts/raw_git_init.py` or `python3 scripts/raw_git_init.py --initial-commit`.
- Raw may use its own dedicated git repository. The wiki should not initialize a nested repo; it should commit through the parent project git repository.

The required loop is:

1. bootstrap or refresh the wiki with helper scripts
2. read raw files one by one
3. editorially update the wiki after each file or small batch
4. rebuild indexes
5. run quality and principle checks
6. fix the failures
7. repeat until the touched area is no longer scaffold-quality

## Ingest

Recommended flow:

1. Read the changed or selected raw files.
2. Use helper scripts for draft generation only when they save time.
3. Distill the material into maintained knowledge instead of mirroring file paths or raw excerpts.
4. Create or update one page in `sources/`.
5. Update the maintained topic page using the configured taxonomy or the fallback destination.
6. Add or improve synthesis under `analyses/` when multiple sources support it.
7. Rebuild indexes with `python3 scripts/wiki_index.py`.
8. Run quality checks:
   `python3 scripts/wiki_quality_audit.py`
   `python3 scripts/wiki_lint.py`
   `python3 scripts/wiki_enforce_principles.py`
9. Rewrite weak generated content before considering the ingest complete.
10. Append a log entry.
11. Commit the coherent wiki batch with `python3 scripts/wiki_commit_batch.py --message "..."`
12. Update sync metadata when the ingest reflects current raw state.

Use:

```bash
python3 scripts/raw_git_status.py
python3 scripts/wiki_sync.py --update-sync-marker
python3 scripts/log_operation.py --operation ingest --update-sync-marker --touched sources/foo.md topics/foo.md
```

If an existing wiki still uses flat `concepts/` or `entities/`, run:

```bash
python3 scripts/migrate_to_hierarchical.py
```

Then rebuild indexes and lint again.

## Query

Start from `index.md`, then read the relevant section indexes and leaf pages. Answer from the wiki first. If the result is valuable long-term, file it back into `analyses/` and log it with `--operation query`.

Default query behavior should be `index-first`. `sources/` is fallback-only unless the maintained hierarchy cannot answer.

## Lint

Look for:

- orphan maintained pages
- stale indexes after edits
- weak backlinks on maintained leaf pages
- contradiction candidates
- missing source summaries for recently changed raw files
- pages that still read like generated scaffolding instead of durable knowledge

Also run:

```bash
python3 scripts/wiki_quality_audit.py
python3 scripts/wiki_lint.py
python3 scripts/wiki_enforce_principles.py
```

Treat failed checks as an editing queue, not as a final report.

## Benchmark

Use `python3 scripts/wiki_benchmark.py` with an external question set when you want to measure whether the maintained hierarchy is producing efficient retrieval. Compare context volume and fallback usage, not just answer presence.

## Taxonomy

The skill manages a generic wiki engine. Taxonomy comes from project config or wiki-local metadata, not from a hardcoded product model.

- If taxonomy is configured, all structure-changing scripts must follow it.
- If taxonomy is absent, the fallback structure is used.
- Do not encode project-specific categories into the shared skill scripts.
