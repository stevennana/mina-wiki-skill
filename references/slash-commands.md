# Slash Commands

These are portable prompt contracts for chat-first LLM CLIs. They are intended to be easy to map into Codex CLI custom commands or Claude Code slash-style prompts.

They do not require a specific CLI plugin format in this repository. The command surface is the behavioral contract the LLM should follow.

To generate reusable prompt files from this contract, run:

```bash
python3 scripts/generate_slash_commands.py
```

By default this creates `generated/slash-commands/codex/`, `generated/slash-commands/claude/`, `generated/slash-commands/manifest.json`, and `generated/slash-commands/codex-commands-snippet.md`.

## Design goals

- short, memorable verbs
- deterministic behavior for common wiki actions
- explicit confirmation for destructive actions
- reuse of helper scripts for path, git, and sync checks

## Command set

### `/wiki-status`

Purpose: report whether the wiki is behind raw.

Behavior:
- run `python3 scripts/check_paths.py`
- run `python3 scripts/wiki_sync_status.py`
- summarize `needs_sync`, raw branch/commit, changed files, and sync reasons

Example prompt:

```text
/wiki-status
```

### `/wiki-sync`

Purpose: update the wiki from raw changes.

Behavior:
- run sync-status first
- if raw has changed, ask the user for approval before editing wiki pages
- after approval, update affected pages, `index.md`, `log.md`, and sync metadata

Example prompt:

```text
/wiki-sync
/wiki-sync sources/article-a.md
```

### `/wiki-add-source`

Purpose: ingest a specific raw source into the wiki.

Arguments:
- raw path relative to `WIKI_RAW_DIR`

Behavior:
- read the source
- create or update a page in `sources/`
- update related entity/concept pages
- refresh `index.md`
- append to `log.md`

Example prompt:

```text
/wiki-add-source articles/llm-wiki.md
```

### `/wiki-update-page`

Purpose: update an existing wiki page from new raw information or session-derived learning.

Arguments:
- wiki page path or logical page name
- optional note about the intended update

Behavior:
- inspect existing page content
- gather supporting raw/wiki context
- revise the page without changing raw files
- update related links if the change affects references
- append to `log.md`

Example prompt:

```text
/wiki-update-page entities/karpathy.md add the latest synthesis from articles/llm-wiki.md
```

### `/wiki-delete-page`

Purpose: delete or archive a wiki page safely.

Arguments:
- wiki page path
- optional replacement page for redirects/manual migration

Behavior:
- require explicit user confirmation
- prefer archive/merge semantics over hard delete when the page has useful history
- remove or repair obvious inbound references
- append a delete/archive entry to `log.md`

Example prompt:

```text
/wiki-delete-page analyses/old-comparison.md
```

### `/wiki-query`

Purpose: answer a question from the wiki and optionally file the answer back.

Arguments:
- natural-language question

Behavior:
- read `index.md` first
- read only relevant pages
- answer with page citations
- if the user asks to save the answer, write it to `analyses/` and log the operation

Example prompt:

```text
/wiki-query What are the core design principles of the LLM Wiki pattern?
```

### `/wiki-lint`

Purpose: health-check the wiki.

Behavior:
- identify stale pages after raw changes
- find orphan pages and weak cross-links
- report contradiction candidates
- suggest missing pages or summaries

Example prompt:

```text
/wiki-lint
```

### `/wiki-log`

Purpose: append a structured log entry for a completed operation.

Behavior:
- use `python3 scripts/log_operation.py`
- include operation name and touched pages
- update sync metadata only when the wiki reflects current raw state

Example prompt:

```text
/wiki-log ingest sources/llm-wiki.md entities/llm.md
```

## Codex CLI usage

For Codex CLI, treat these as stable command-shaped prompts. A practical pattern is to keep them in your operator notes or project prompt library and invoke them exactly as written.

If the adopting project has an `AGENTS.md`, inject the generated `Codex Wiki Commands` snippet there and point it at `generated/slash-commands/codex/`.

Recommended commands:

- `/wiki-status`
- `/wiki-sync`
- `/wiki-add-source <raw-path>`
- `/wiki-update-page <wiki-path> [instruction]`
- `/wiki-delete-page <wiki-path>`
- `/wiki-query <question>`
- `/wiki-lint`
- `/wiki-log <operation> [touched pages...]`

Codex should map each command to the behavior above and use the helper scripts when possible.

## Claude Code usage

For Claude Code, use the same command names and semantics. If you maintain a project-level `CLAUDE.md`, mirror this command table there so Claude sessions follow the same workflow as Codex sessions.

Recommended Claude Code operator prompts:

```text
/wiki-status
/wiki-sync
/wiki-add-source notes/book-chapter-01.md
/wiki-update-page concepts/knowledge-compounding.md refine the summary and add links
/wiki-query Summarize the difference between raw sources and wiki pages.
```

## Safety rules

- Never modify files in `WIKI_RAW_DIR`.
- Always ask for confirmation before delete/archive operations.
- Ask for approval before sync-driven wiki edits when raw has advanced.
- Prefer updating existing pages over creating near-duplicates.
- Always update `log.md` after a wiki-changing command.
