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
2. Distill them into standalone wiki knowledge instead of mirroring file paths or raw excerpts.
3. Create or update one page in `sources/`.
4. Update any impacted pages in `entities/`, `concepts/`, or `analyses/`.
5. Add or revise the page entry in `index.md`.
6. Append a log entry.
7. Update sync metadata when the ingest reflects current raw state.

Use:

```bash
python3 scripts/raw_git_status.py
python3 scripts/wiki_sync.py --update-sync-marker
python3 scripts/log_operation.py --operation ingest --update-sync-marker --touched sources/foo.md entities/bar.md
```

`python3 scripts/wiki_sync.py --update-sync-marker` is the preferred full-directory operation for:
- initial wiki bootstrap from the current raw tree
- updates to existing raw files
- new raw files
- raw-file deletions that should remove their corresponding `sources/` pages

When a prior generated pass needs to be replaced cleanly, run `python3 scripts/wiki_sync.py --reset-generated --update-sync-marker` to rebuild `sources/`, `entities/`, `concepts/`, `analyses/`, `index.md`, `log.md`, and sync metadata while leaving unrelated files like `.obsidian/` intact.

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
---
```

Prefer stable page placement and deterministic names so multiple sessions update the same pages instead of creating near-duplicates.
Prefer visible page content that reads like maintained knowledge, not sync bookkeeping. Keep raw-to-page mappings and similar operational state under `.steven-wiki/`.
