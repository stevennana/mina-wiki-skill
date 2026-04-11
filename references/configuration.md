# Configuration

## Directory contract

The skill uses two external directories:

- `WIKI_RAW_DIR`: raw sources, read-only from the skill's point of view, optional input for ingestion and sync
- `WIKI_DIR`: shared wiki, writable by adopted LLM CLI sessions

The skill never mutates raw files.

## Resolution order

Paths are resolved in this order:

1. environment variables `WIKI_RAW_DIR` and `WIKI_DIR`
2. JSON config file from `STEVEN_WIKI_CONFIG`
3. nearest `.steven-wiki.json` found by walking from the current working directory toward `/`

## Config schema

Minimal JSON:

```json
{
  "raw_dir": "/absolute/path/to/raw",
  "wiki_dir": "/absolute/path/to/wiki"
}
```

Supported aliases:
- `WIKI_RAW_DIR`
- `WIKI_DIR`

Use env vars to override config per project or per session.

## User guidance pattern

When a user wants to start using the skill but the environment is not configured yet:

1. Explain `WIKI_RAW_DIR` and `WIKI_DIR` in plain terms.
2. Offer two setup paths:
   - global shell setup in `~/.zprofile` or `~/.zshrc`
   - project-local `.steven-wiki.json`
3. Offer to perform the configuration on the user's behalf.
4. If a shell profile was edited, remind the user to run:

```bash
source ~/.zprofile
```

or:

```bash
source ~/.zshrc
```

Use shell-profile setup when the same raw/wiki roots should apply across many sessions. Use `.steven-wiki.json` when a specific project should override the default roots.

## Sync metadata

The skill stores sync metadata in:

`WIKI_DIR/.steven-wiki/last_sync.json`

This file records the last raw commit and dirty-state snapshot that were successfully incorporated into the wiki. Raw freshness checks compare the current raw git state against this marker.

The skill may also keep sync bookkeeping such as source-to-page mappings under `WIKI_DIR/.steven-wiki/`. That metadata supports maintenance workflows and should not be treated as part of the user-facing wiki content model.
