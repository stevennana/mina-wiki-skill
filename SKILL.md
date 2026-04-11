---
name: steven-wiki-skill
description: Maintain a shared markdown wiki from raw source directories and session-derived knowledge. Use when an adopted LLM CLI project should detect raw updates, sync wiki pages, answer from the wiki, or lint a persistent knowledge base backed by WIKI_RAW_DIR and WIKI_DIR.
---

This skill turns an adopted LLM CLI session into a disciplined wiki maintainer following the LLM Wiki pattern.

## When To Use

Use this skill when:
- a project/session has access to `WIKI_RAW_DIR` and `WIKI_DIR`
- the user wants to ingest or re-sync raw sources into the shared wiki
- the user wants answers grounded in the maintained wiki instead of re-deriving from raw files
- the user wants to file analysis back into the wiki
- the user wants to check whether the wiki is behind the raw git repo

Do not modify files in `WIKI_RAW_DIR`. Raw is read-only source-of-truth input.

## Required Environment

Resolve directories in this order:
1. `WIKI_RAW_DIR` and `WIKI_DIR`
2. optional config file from `STEVEN_WIKI_CONFIG`
3. optional `.steven-wiki.json` discovered in the current project or a parent directory

When the user asks to use this skill and the environment is not configured yet, guide them to set the directories in either:
- shell session startup files such as `~/.zprofile` or `~/.zshrc`
- a project-local `.steven-wiki.json`

Preferred guidance:
- explain the two variables and what they point to
- offer to configure them on the user's behalf if editing their shell profile or project config is appropriate
- after editing a shell profile, remind the user to run `source ~/.zprofile` or `source ~/.zshrc`, or start a new shell session
- for project-specific setup, prefer `.steven-wiki.json` when different projects should point at different wiki roots or when the user does not want global shell changes

Validate paths before substantive work:

```bash
python3 scripts/check_paths.py
python3 scripts/wiki_sync_status.py
```

`WIKI_RAW_DIR` must be a git repo. `WIKI_DIR` must be writable by the current session.

## Session-Start Workflow

At the start of an adopted CLI session:
1. Run `python3 scripts/wiki_sync_status.py`.
2. If `needs_sync` is `true`, tell the user raw has changed and ask whether to update the wiki now.
3. If accepted, inspect the changed raw files, update affected wiki pages, refresh `index.md`, append `log.md`, then record the new sync marker.
4. If declined, continue but state that the wiki may lag raw.

The helper script reports freshness. The user approval step stays in the conversation layer.

## Core Operations

### Ingest

- Read one or a few raw files at a time.
- Create or update a source page under `sources/`.
- Update linked entity/concept/analysis pages as needed.
- Refresh `index.md`.
- Append a chronological entry to `log.md`.
- After a successful raw-driven sync, update the sync marker:

```bash
python3 scripts/log_operation.py --operation ingest --update-sync-marker --touched sources/example.md entities/topic.md
```

### Query

- Read `index.md` first to find relevant pages.
- Read only the pages needed to answer.
- Cite wiki pages explicitly in the answer.
- If the result is durable knowledge, file it under `analyses/` or another appropriate page and log it.

### Lint

- Look for stale claims versus newer raw changes.
- Find orphan pages, missing cross-links, weak summaries, and contradiction candidates.
- Suggest which raw sources or wiki pages need review.

## Wiki Conventions

- Keep the shared wiki Obsidian-friendly and markdown-first.
- Prefer directories such as `sources/`, `entities/`, `concepts/`, and `analyses/`.
- `index.md` is the catalog. `log.md` is append-only chronology.
- Use wiki links like `[[entities/example-topic]]`.
- Optional frontmatter is allowed for `type`, `sources`, `last_reviewed`, and `raw_commit`.

Read [references/configuration.md](references/configuration.md) for path/config details and [references/operations.md](references/operations.md) for workflow and page conventions. Use the helper scripts in `scripts/` for deterministic checks and logging instead of re-implementing them in chat.

For reusable operator shortcuts, read [references/slash-commands.md](references/slash-commands.md). Use those prompt contracts when the user wants command-like wiki operations such as add, update, delete, sync, query, or lint from Codex CLI or Claude Code.
