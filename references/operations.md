# Operations

## Session start

Run `python3 scripts/wiki_sync_status.py` first.

- If `needs_sync` is `false`, continue normally.
- If `needs_sync` is `true`, tell the user raw has changed and ask whether to sync the wiki now.
- If accepted, inspect the changed raw files, update affected wiki pages, refresh `index.md`, append to `log.md`, and update the sync marker.
- If `baseline_commit_recommended` is `true`, treat the run as an initial bootstrap. Finish the first useful wiki sync, then create the first commit in `WIKI_RAW_DIR` so future sync checks can compare git state cleanly.
- If raw is not a git repo yet, bootstrap the wiki first, then run `python3 scripts/raw_git_init.py` or `python3 scripts/raw_git_init.py --initial-commit`.
- If you want commit-backed wiki history and `WIKI_DIR` is not a git repo yet, run `python3 scripts/wiki_git_init.py` or `python3 scripts/wiki_git_init.py --initial-commit`.

The required loop is:

1. bootstrap or refresh the wiki with helper scripts
2. read raw files one by one
3. editorially update the wiki after each file or small batch
4. run quality checks
5. fix the failures
6. repeat until the touched area is no longer scaffold-quality

## Ingest

Recommended flow:

1. Read the changed or selected raw files.
2. Use helper scripts for draft generation only when they save time.
3. Distill the material into standalone wiki knowledge instead of mirroring file paths or raw excerpts.
4. Create or update one page in `sources/`.
5. Update any impacted pages in `entities/`, `concepts/`, or `analyses/`.
6. Continue file by file instead of stopping after one or two rewrites if the user asked for the wiki to be upgraded.
7. Run quality checks:
   `python3 scripts/wiki_quality_audit.py`
   `python3 scripts/wiki_lint.py`
8. Rewrite weak generated content before considering the ingest complete.
9. Add or revise the page entry in `index.md`.
10. Append a log entry.
11. Commit the coherent wiki batch with `python3 scripts/wiki_commit_batch.py --message "..."`
12. Update sync metadata when the ingest reflects current raw state.

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

This command should be treated as a bootstrap and maintenance aid, not as the final author of the wiki. The LLM should inspect the touched pages, improve weak summaries, merge duplicated concepts, add synthesis pages, and prune low-value pages after generation.

When a prior generated pass needs to be replaced cleanly, run `python3 scripts/wiki_sync.py --reset-generated --update-sync-marker` to rebuild `sources/`, `entities/`, `concepts/`, `analyses/`, `index.md`, `log.md`, and sync metadata while leaving unrelated files like `.obsidian/` intact.

After either sync command, the editorial pass is mandatory. The wiki is not considered maintained until the LLM has:
- removed obvious placeholder text from the touched area
- rewritten clipped or extractive summaries
- added synthesis where multiple pages clearly belong to a larger pattern
- rerun the quality checks and responded to what they found

## Query

Start from `index.md`, then read only relevant pages. Answer from the wiki first. If the result is valuable long-term, file it back into the wiki and log it with `--operation query`.

## Lint

Look for:
- orphan pages
- stale summaries after raw updates
- pages missing obvious back-links
- contradiction candidates
- missing source summaries for recently changed raw files
- pages that still read like generated scaffolding instead of durable knowledge

Also run:

```bash
python3 scripts/wiki_quality_audit.py
python3 scripts/wiki_lint.py
```

Treat failed checks as an editing queue, not as a final report.

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
