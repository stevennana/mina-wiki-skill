# Steven Wiki Skill

`steven-wiki-skill` is a Codex-style skill for maintaining a shared markdown wiki from a raw source directory and ongoing LLM session work.

It follows the "LLM Wiki" pattern:
- raw files are the source of truth
- the wiki is the maintained, interlinked knowledge layer
- the skill gives the LLM a repeatable workflow for ingest, query, sync, and lint

## Core idea

The skill works with two external directories:

- `WIKI_RAW_DIR`: raw source files, treated as read-only by the skill
- `WIKI_DIR`: shared wiki pages, updated by adopted LLM CLI sessions

The raw directory must be its own git repository. The skill uses git state to detect whether the wiki is behind the latest raw changes.

When an adopted LLM CLI session starts, it can:
1. check whether raw has changed
2. ask the user whether to sync the wiki now
3. update affected wiki pages if the user accepts

This keeps the wiki current while still leaving the user in control of when updates happen.

## Repository layout

- `SKILL.md`: the actual skill instructions loaded by Codex
- `agents/openai.yaml`: UI metadata for the skill
- `references/`: supporting documentation for config and operations
- `references/slash-commands.md`: portable slash-command prompt contracts
- `scripts/`: deterministic helper scripts
- `tests/`: unit tests for helper behavior

## Configuration

The skill resolves directories in this order:

1. `WIKI_RAW_DIR` and `WIKI_DIR`
2. `STEVEN_WIKI_CONFIG`
3. `.steven-wiki.json` in the current project or a parent directory

Example config file:

```json
{
  "raw_dir": "/absolute/path/to/raw",
  "wiki_dir": "/absolute/path/to/wiki"
}
```

Recommended environment variables:

```bash
export WIKI_RAW_DIR=/path/to/raw
export WIKI_DIR=/path/to/wiki
```

If you want the variables available in every shell session, add them to `~/.zprofile` or `~/.zshrc`:

```bash
export WIKI_RAW_DIR=/path/to/raw
export WIKI_DIR=/path/to/wiki
```

Then reload your shell configuration:

```bash
source ~/.zprofile
```

or:

```bash
source ~/.zshrc
```

If you prefer project-specific setup, create `.steven-wiki.json` in the project root instead of changing your global shell profile.

When helping a user interactively, the assistant should explicitly offer:
- to configure `WIKI_RAW_DIR` and `WIKI_DIR` on the user's behalf
- to use shell-profile setup for all sessions
- or to use `.steven-wiki.json` for project-local configuration

## Helper commands

Validate configuration:

```bash
python3 scripts/check_paths.py
```

Inspect raw git state:

```bash
python3 scripts/raw_git_status.py
```

Check whether the wiki is behind raw:

```bash
python3 scripts/wiki_sync_status.py
```

Create the minimal wiki structure:

```bash
python3 scripts/bootstrap_wiki.py
```

Append a log entry and update the sync marker:

```bash
python3 scripts/log_operation.py \
  --operation ingest \
  --touched sources/example.md entities/topic.md \
  --update-sync-marker
```

Generate reusable slash-command prompt files for Codex CLI and Claude Code:

```bash
python3 scripts/generate_slash_commands.py
```

Run tests:

```bash
make test
```

## Expected wiki structure

Inside `WIKI_DIR`, the skill expects or can create:

- `index.md`: content catalog
- `log.md`: append-only operation history
- `sources/`: source summaries
- `entities/`: entity pages
- `concepts/`: concept pages
- `analyses/`: filed query results and synthesis
- `.steven-wiki/last_sync.json`: sync metadata

## Typical workflow

1. Put source files into `WIKI_RAW_DIR`.
2. Start an adopted LLM CLI session with access to both directories.
3. Run or trigger `scripts/wiki_sync_status.py`.
4. If raw has changed, approve the wiki update.
5. Let the skill update wiki pages, `index.md`, `log.md`, and the sync marker.
6. Ask questions against the wiki and file durable answers back into it.

## Prompt-based slash commands

This repo also defines a portable slash-command layer for chat-based CLI tools such as Codex CLI and Claude Code. These are prompt contracts, not shell aliases. They give the LLM a stable interface for common wiki actions.

Included command families:

- `/wiki-status`: inspect raw/wiki freshness
- `/wiki-sync`: ask for approval, then sync wiki from raw
- `/wiki-add-source`: ingest a specific raw file into the wiki
- `/wiki-update-page`: revise an existing wiki page
- `/wiki-delete-page`: delete or archive a wiki page and clean references
- `/wiki-query`: answer from wiki pages and optionally file the result
- `/wiki-lint`: health-check the wiki for stale content and missing links
- `/wiki-log`: append a structured operation entry

See [references/slash-commands.md](references/slash-commands.md) for the expected arguments, behavior, and example invocations for both Codex CLI and Claude Code.

To generate ready-to-copy command prompt files, run `python3 scripts/generate_slash_commands.py`. By default it writes:

- `generated/slash-commands/codex/*.md`
- `generated/slash-commands/claude/*.md`
- `generated/slash-commands/manifest.json`

## Notes

- The skill never modifies raw files.
- Multiple adopted projects can share the same wiki.
- Session-derived knowledge can also be written back into the wiki, not only raw-ingested knowledge.
