# Operations

## Session start

Run `python3 scripts/wiki_sync_status.py` first.

- If `needs_sync` is `false`, continue normally.
- If `needs_sync` is `true`, tell the user raw has changed and ask whether to sync the wiki now.
- If accepted, inspect the changed raw files, update affected wiki pages, refresh `index.md`, append to `log.md`, and update the sync marker.
- If `baseline_commit_recommended` is `true`, treat the run as an initial bootstrap. Finish the first useful wiki sync, then create the first commit in `WIKI_RAW_DIR` so future sync checks can compare git state cleanly.

## Ingest

Recommended flow:

1. Read the changed or selected raw files.
2. Create or update one page in `sources/`.
3. Update any impacted pages in `entities/`, `concepts/`, or `analyses/`.
4. Add or revise the page entry in `index.md`.
5. Append a log entry.
6. Update sync metadata when the ingest reflects current raw state.

Use:

```bash
python3 scripts/raw_git_status.py
python3 scripts/log_operation.py --operation ingest --update-sync-marker --touched sources/foo.md entities/bar.md
```

## Query

Start from `index.md`, then read only relevant pages. Answer from the wiki first. If the result is valuable long-term, file it back into the wiki and log it with `--operation query`.

## Lint

Look for:
- orphan pages
- stale summaries after raw updates
- pages missing obvious back-links
- contradiction candidates
- missing source summaries for recently changed raw files

## Page shape

Keep pages concise and cross-linked. Optional frontmatter example:

```yaml
---
type: entity
sources:
  - sources/example-source
last_reviewed: 2026-04-11
raw_commit: abc1234
---
```

Prefer stable page placement and deterministic names so multiple sessions update the same pages instead of creating near-duplicates.
