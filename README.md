# Steven Wiki Skill

`steven-wiki-skill` is a Codex-style skill for maintaining a shared markdown wiki from a raw source directory and ongoing LLM session work.

This project is inspired by Andrej Karpathy's [LLM Wiki](https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw/ac46de1ad27f92b28ac95459c782c07f6b8c964a/llm-wiki.md) concept: a persistent, LLM-maintained wiki that sits between raw source material and query-time answers.

It follows the "LLM Wiki" pattern:
- raw files are optional input material for ingestion
- the wiki is the maintained, interlinked knowledge layer
- the skill gives the LLM a repeatable workflow for ingest, query, sync, and lint

## Core idea

The skill works with two external directories:

- `WIKI_RAW_DIR`: raw source files, treated as read-only by the skill
- `WIKI_DIR`: shared wiki pages, updated by adopted LLM CLI sessions

The wiki is the primary artifact. The LLM should write pages that stand on their own, integrating knowledge from raw material instead of mirroring file paths or dumping raw excerpts. The raw directory is read-only input and optional after ingestion. The skill uses git state to detect whether the wiki is behind the latest raw changes when `WIKI_RAW_DIR` is present.

If the raw repo has not been committed yet, the workflow treats that as an initial bootstrap phase:
- ingest the current raw tree into the wiki first
- once the wiki is implemented enough to reflect that initial tree, create the first commit in `WIKI_RAW_DIR`
- use that baseline commit plus sync metadata for future change detection

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

## Install

### Codex CLI

Install this repository as a local Codex skill by copying or linking it into your Codex skills directory as `steven-wiki-skill`.

Typical local install:

```bash
mkdir -p ~/.codex/skills
ln -s /absolute/path/to/steven-wiki-skill ~/.codex/skills/steven-wiki-skill
```

If you prefer a plain copy instead of a symlink:

```bash
mkdir -p ~/.codex/skills
cp -R /absolute/path/to/steven-wiki-skill ~/.codex/skills/steven-wiki-skill
```

After installation, restart Codex so it reloads available skills.

You can then invoke it explicitly in Codex with prompts such as:

```text
Use $steven-wiki-skill to check whether my wiki is behind raw and guide me through sync.
```

### Claude Code

Claude Code does not use this exact Codex skill packaging format directly, so the practical installation path is:

1. clone or keep this repository locally
2. point Claude Code sessions at the same `WIKI_RAW_DIR` and `WIKI_DIR`
3. copy the workflow rules from `SKILL.md` into your project-level `CLAUDE.md`
4. optionally generate the slash-command prompt files with `python3 scripts/generate_slash_commands.py`

Recommended Claude project setup:

```text
- keep this repo available locally as the source of truth
- mirror the operational rules into CLAUDE.md
- reuse generated files from generated/slash-commands/claude/
```

This keeps Codex and Claude aligned on the same wiki workflow even though their packaging conventions differ.

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

If this reports `baseline_commit_recommended: true`, finish the initial wiki sync first, then create the first commit in `WIKI_RAW_DIR` so later syncs can rely on git history instead of only a dirty working tree.

Create the minimal wiki structure:

```bash
python3 scripts/bootstrap_wiki.py
```

Sync the wiki from the full raw directory:

```bash
python3 scripts/wiki_sync.py --update-sync-marker
```

Use this for the initial wiki bootstrap and for later raw update/delete/add passes.

If you need to rebuild the generated wiki pages from scratch while preserving local vault settings such as `.obsidian/`, use:

```bash
python3 scripts/wiki_sync.py --reset-generated --update-sync-marker
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

Ingest a raw file into the wiki:

```bash
python3 scripts/wiki_ingest.py tickets/commands.md --update-sync-marker
```

Rebuild the wiki index:

```bash
python3 scripts/wiki_index.py
```

Run a wiki-grounded query and save the result:

```bash
python3 scripts/wiki_query.py "What does this wiki say about event mesh?" --save-to event-mesh-answer
```

Lint the wiki for stale or weak structure:

```bash
python3 scripts/wiki_lint.py
```

Check session-start sync state:

```bash
python3 scripts/wiki_session_start.py
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
