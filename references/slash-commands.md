# Slash Commands

## `/wiki-status`

- run `python3 scripts/check_paths.py`
- run `python3 scripts/wiki_sync_status.py`
- summarize `needs_sync`, raw branch and commit, changed files, and sync reasons

## `/wiki-sync`

- run sync status first
- if raw changed, ask the user for approval before editing wiki pages
- after approval, run `python3 scripts/wiki_sync.py --update-sync-marker`
- update affected maintained pages, rebuild root and section indexes, append to `log.md`, and refresh sync metadata

Example:

```text
/wiki-sync
```

## `/wiki-add-source`

- read the raw source relative to `WIKI_RAW_DIR`
- create or update a page in `sources/`
- update the maintained topic page using configured taxonomy or fallback destination
- rebuild indexes and append to `log.md`

Example:

```text
/wiki-add-source docs/example-source.md
```

## `/wiki-update-page`

- inspect the existing page and gather relevant raw or wiki context
- revise the target page without changing raw files
- repair nearby links and append to `log.md`

Example:

```text
/wiki-update-page topics/example-topic.md refine the explanation and add source coverage
```

## `/wiki-query`

- read `index.md` first
- read only the relevant section indexes and leaf pages
- keep `sources/` as fallback only unless the maintained hierarchy is insufficient
- answer with citations to wiki pages
- if the user asks to save the result, write it to `analyses/` and log the operation

Example:

```text
/wiki-query What does the example topic cover in this system?
```

## `/wiki-lint`

- identify orphan maintained pages
- find weak backlinks, contradiction candidates, and missing summaries
- treat the output as an editing queue

## `/wiki-benchmark`

- run `python3 scripts/wiki_benchmark.py` with an external question set
- measure elapsed time, matched pages, cited context, and sources fallback usage
- use it to validate whether the hierarchy helps real retrieval

## `/wiki-log`

- use `python3 scripts/log_operation.py`
- include operation name and touched pages
- update sync metadata only when the wiki reflects current raw state

Example:

```text
/wiki-log ingest sources/example-source.md topics/example-topic.md
```
