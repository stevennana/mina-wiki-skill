# mina-wiki-skill

`mina-wiki-skill` is a Codex-style skill for maintaining a general-purpose markdown wiki from a raw source directory and ongoing LLM session work.

The wiki is the maintained knowledge layer. Raw files are ingestion input. Scripts in this repo help bootstrap, sync, index, lint, and log the wiki, but the LLM still owns the editorial work.

## Structure

The maintained wiki always includes:

- `index.md`: root navigation entrypoint
- `sources/`: raw source summaries
- `analyses/`: synthesis and filed answers
- `legacy/`: archived pages from older structures
- `.mina-wiki/`: operational metadata including local taxonomy state

Additional maintained sections come from taxonomy config. If no taxonomy is configured, the built-in fallback creates `topics/`, `analyses/`, `sources/`, and `legacy/`.

The skill does not hardcode one product or domain taxonomy as the default structure.

## Taxonomy Configuration

Taxonomy can be supplied in one of these ways:

1. inline in `.mina-wiki.json` under `taxonomy`
2. by path using `WIKI_TAXONOMY_CONFIG` or config field `taxonomy_config`
3. as wiki-local metadata in `WIKI_DIR/.mina-wiki/taxonomy.json`
4. omitted entirely, in which case the fallback structure is used

Example inline taxonomy:

```json
{
  "raw_dir": "/absolute/path/to/raw",
  "wiki_dir": "/absolute/path/to/wiki",
  "taxonomy": {
    "root_sections": ["sections", "analyses", "sources", "legacy"],
    "section_descriptions": {
      "sections": "Maintained topical knowledge.",
      "sections/example-subsection": "Example subsection for project-specific material."
    },
    "children": {
      "sections": ["example-subsection", "reference"]
    },
    "default_destination": "sections",
    "routing_rules": [
      {
        "pattern": "example keyword",
        "destination": "sections/example-subsection",
        "match": "any"
      }
    ]
  }
}
```

## Core Commands

Validate configuration:

```bash
python3 scripts/check_paths.py
```

Check whether the wiki is behind raw:

```bash
python3 scripts/wiki_sync_status.py
```

Bootstrap the configured wiki structure:

```bash
python3 scripts/bootstrap_wiki.py
```

Sync the wiki from the full raw directory:

```bash
python3 scripts/wiki_sync.py --update-sync-marker
```

Rebuild root and section indexes:

```bash
python3 scripts/wiki_index.py
```

Migrate an old flat wiki:

```bash
python3 scripts/migrate_to_hierarchical.py
```

Run editorial quality checks:

```bash
python3 scripts/wiki_quality_audit.py
python3 scripts/wiki_lint.py
```

Append a log entry:

```bash
python3 scripts/log_operation.py \
  --operation ingest \
  --touched sources/example-source.md topics/example-topic.md \
  --update-sync-marker
```

## Testing

Run:

```bash
make test
```

The tests cover config resolution, sync-state detection, fallback taxonomy behavior, custom taxonomy behavior, index rebuilds, ingest behavior, query save flow, migration flow, and sync cleanup behavior.
