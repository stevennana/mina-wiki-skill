# Repository Guidelines

## Project Structure & Module Organization
This repository is a Codex skill project. The root `SKILL.md` defines the runtime behavior the LLM should follow. UI metadata lives in `agents/openai.yaml`. Detailed operating rules belong in `references/`, and deterministic helpers live in `scripts/`. Tests for helper scripts belong in `tests/`.

Keep the wiki-specific logic in the helper layer, not duplicated across docs. Example paths:
- `scripts/wiki_common.py` for shared path, git, and sync helpers
- `scripts/wiki_sync_status.py` for raw-vs-wiki freshness checks
- `references/operations.md` for ingest/query/lint workflow details

## Build, Test, and Development Commands
- `make test`: run the Python unit test suite
- `python3 scripts/check_paths.py`: resolve `WIKI_RAW_DIR` and `WIKI_DIR`, then validate access
- `python3 scripts/raw_git_status.py`: inspect raw git state
- `python3 scripts/wiki_sync_status.py`: report whether the wiki is behind raw

The helper scripts use only the Python standard library. No install step is required for local development.

## Coding Style & Naming Conventions
Use Python 3 with 4-space indentation and type hints where they improve clarity. Keep scripts small and composable. Prefer snake_case for Python modules, functions, JSON keys, and config fields. Use concise Markdown headings and markdown wiki-link examples in docs.

Environment variables are uppercase and fixed:
- `WIKI_RAW_DIR`
- `WIKI_DIR`
- optional `STEVEN_WIKI_CONFIG`

## Local Default Paths
Use these defaults for local development and manual test runs in this repository unless the user provides different paths:
- `WIKI_RAW_DIR=/Users/stevenna/wiki/raw`
- `WIKI_DIR=/Users/stevenna/wiki/llm-wiki`

When verifying helper scripts manually, prefer exporting these values for the command being tested.

## Testing Guidelines
Write tests under `tests/` using `unittest`. Name files `test_*.py`. Cover config resolution, git detection, sync-state calculations, and failure cases for missing or invalid directories. Use temporary directories and short-lived git repos in tests instead of fixture state.

## Commit & Pull Request Guidelines
Use short imperative commit messages such as `Add raw sync status helper` or `Document wiki session-start flow`. Pull requests should include the workflow change, affected scripts/docs, and a short note about how the change was verified. Include command output summaries when you modify sync detection or logging behavior.
