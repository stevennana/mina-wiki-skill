# mina-wiki-skill

`mina-wiki-skill` is a shared wiki workflow for AI coding agents such as Codex and Claude.

It gives your project a long-lived markdown knowledge base so the agent can:

- ingest raw source material into a maintained wiki
- answer project questions from the wiki first
- keep indexes, topic pages, analyses, and source summaries in sync
- measure and enforce wiki quality over time

If you want your project to build up memory instead of re-deriving context every session, this repository is for that workflow.

## Why This Is Better Than A Generic “LLM Wiki”

Many LLM wiki setups stop at:

- collect markdown
- let the agent search it later
- hope the structure stays useful

This workflow is stronger because it defines the whole operating model:

- **raw and wiki are different surfaces**
  Raw is ingestion input. The wiki is the maintained memory.
- **retrieval has a strategy**
  The default path is `index.md -> section index -> leaf page`, not “scan everything.”
- **the wiki has an explicit structure**
  `index.md`, maintained sections, `sources/`, `analyses/`, `legacy/`, and taxonomy all have specific roles.
- **quality is part of operation**
  Sync checks, lint, audits, principles enforcement, and benchmarks are built in.
- **it integrates with agent workflows**
  It is designed to be injected into `AGENTS.md` and `CLAUDE.md`, not left as an isolated doc dump.
- **git boundaries are intentional**
  Raw can be separate. Wiki history belongs to the parent project repo.

The result is not just “some markdown exists.”  
The result is a wiki that agents can actually navigate, trust, benchmark, and improve over time.

## Data Flow

This is the key mental model for how the system works.

### 1. Raw Goes In

You put source material into `WIKI_RAW_DIR`.

Examples:

- copied docs
- research notes
- exported support content
- design docs
- external references
- code-adjacent technical notes

Raw is ingestion input, not the final knowledge surface.

### 2. The Agent Transforms It

You ask Codex or Claude to use the wiki workflow.

Typical request:

```text
Use mina-wiki-skill for this project.
Check whether the wiki is behind raw, sync it if needed, and improve the touched pages.
```

The agent then:

1. checks sync state
2. reads raw files
3. creates or updates `sources/` summaries
4. routes content into maintained topic pages using taxonomy or fallback structure
5. rebuilds indexes
6. runs quality checks
7. improves weak pages

### 3. A Maintained Wiki Comes Out

At minimum, the wiki looks like this:

```text
WIKI_DIR/
  index.md
  topics/
    index.md
    <topic>.md
  analyses/
    index.md
    <analysis>.md
  sources/
    index.md
    <source-summary>.md
  legacy/
    index.md
    ...
  .mina-wiki/
    last_sync.json
    source_map.json
    taxonomy.json
    benchmarks/
      baseline.json
```

If a project defines a richer taxonomy, the maintained structure becomes more specific:

```text
WIKI_DIR/
  index.md
  sections/
    index.md
    api/
      index.md
      auth.md
    runtime/
      index.md
      event-loop.md
  analyses/
  sources/
  legacy/
  .mina-wiki/
```

### 4. Retrieval Uses The Maintained Surface

Once the wiki exists, ordinary question-answering should go through:

1. root `index.md`
2. relevant section indexes
3. relevant leaf pages
4. `sources/` only if the maintained structure cannot answer

That is why the wiki stays efficient. The workflow is designed to prevent the system from collapsing back into raw-first browsing.

## First: What You Actually Do With This

You typically have:

- `WIKI_RAW_DIR`
  Raw source material. This is ingestion input.
- `WIKI_DIR`
  The maintained wiki. This becomes the project’s durable memory.

Then you use Codex or Claude to:

1. check whether raw changed
2. sync the wiki when needed
3. improve the maintained pages editorially
4. query the wiki with an `index-first` approach
5. run lint / audit / benchmark checks

This is **not** an Obsidian workflow.

- It does not assume `.obsidian/`.
- It does not rely on Obsidian plugin metadata.
- It is a markdown-first, agent-maintained knowledge system.

You can open the files in Obsidian if you want, but Obsidian is not part of the operating model.

## Quick Start

### 1. Install For Codex

If you use Codex skills locally, install this repository into your Codex skills directory.

Typical local install:

```bash
mkdir -p ~/.codex/skills
ln -s /absolute/path/to/mina-wiki-skill ~/.codex/skills/mina-wiki-skill
```

If you prefer copying instead of symlinking:

```bash
mkdir -p ~/.codex/skills
cp -R /absolute/path/to/mina-wiki-skill ~/.codex/skills/mina-wiki-skill
```

After that, restart Codex so it reloads available skills.

### 2. Install For Claude

Claude should be treated as a separate integration path, not as “Codex but with different prompts”.

Based on Anthropic’s official Claude Code docs, the practical setup is:

1. install **Claude Code** itself
2. make this repository available locally
3. expose the workflow to Claude using project instructions and/or Claude skills

#### Install Claude Code

Anthropic’s official install methods include:

- native installer
- Homebrew
- WinGet
- npm

Examples from the official docs:

```bash
npm install -g @anthropic-ai/claude-code
```

or on macOS/Linux/WSL:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

After installation, start Claude Code in the target project:

```bash
cd /path/to/your/project
claude
```

Claude Code will handle authentication when you launch it.

#### Make This Wiki Workflow Available To Claude

Claude Code supports:

- project instructions via `CLAUDE.md` or `.claude/CLAUDE.md`
- reusable skills under `~/.claude/skills/` or project-local `.claude/skills/`
- custom slash-command style prompts through markdown files and skills

For this repository, the practical options are:

1. keep this repository available locally
2. configure the same `WIKI_RAW_DIR` and `WIKI_DIR`
3. inject the generated wiki guidance into the target project’s `CLAUDE.md`
4. optionally install or symlink this repository into Claude’s skills directory if you want native Claude skill discovery

Generate the reusable project snippets with:

```bash
python3 scripts/generate_slash_commands.py
```

This creates:

- `generated/slash-commands/claude-wiki-snippet.md`
- `generated/slash-commands/agents-wiki-snippet.md`
- `generated/slash-commands/codex-commands-snippet.md`

For Claude, the most important file is:

- `generated/slash-commands/claude-wiki-snippet.md`

Copy that into the receiving project’s `CLAUDE.md` or `.claude/CLAUDE.md`.

#### Optional: Install As A Claude Skill

Claude Code can discover skills from:

- `~/.claude/skills/`
- `.claude/skills/` inside the project

If you want this repository available as a native Claude skill, place or symlink it so Claude sees a skill directory with `SKILL.md` at its entrypoint. A typical user-level setup is:

```bash
mkdir -p ~/.claude/skills
ln -s /absolute/path/to/mina-wiki-skill ~/.claude/skills/mina-wiki-skill
```

If you prefer project-local scope:

```bash
mkdir -p .claude/skills
ln -s /absolute/path/to/mina-wiki-skill .claude/skills/mina-wiki-skill
```

Claude Code watches skill directories for changes, but if you create the top-level skills directory for the first time, restarting Claude Code is the safest choice.

Verified local install example:

```bash
mkdir -p ~/.claude/skills
ln -s /absolute/path/to/mina-wiki-skill ~/.claude/skills/mina-wiki-skill
```

In this repository, that exact install pattern was tested successfully with Claude Code.

### 3. Configure A Project

The easiest project-local setup is `.mina-wiki.json` in the target project root:

```json
{
  "raw_dir": "/absolute/path/to/raw",
  "wiki_dir": "/absolute/path/to/wiki"
}
```

You can also use environment variables:

```bash
export WIKI_RAW_DIR=/absolute/path/to/raw
export WIKI_DIR=/absolute/path/to/wiki
```

Optional taxonomy can also live in `.mina-wiki.json`:

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

### 4. Start Using It In Codex

Once installed and configured, start a Codex session in the target project and explicitly invoke the skill.

Typical prompts:

```text
Use mina-wiki-skill for this project.
Check whether the wiki is behind raw, and if it is, guide me through syncing it.
```

or:

```text
Use mina-wiki-skill to answer from the wiki first, and only fall back to raw if needed.
```

If you also inject the generated wiki section into the project’s `AGENTS.md`, future Codex sessions can follow the workflow without you re-explaining it every time.

### 5. Start Using It In Claude

After you either:

- add the generated guidance to `CLAUDE.md`, or
- install this repository into a Claude skills directory,

open Claude Code in the project and ask it to work through the wiki workflow directly.

Typical prompts:

```text
Check the wiki sync status and tell me if raw changed.
```

```text
Use the wiki as the first source of truth and answer this question.
```

```text
Run the wiki quality checks and tell me what needs fixing.
```

You can also verify that Claude sees the installed skill by asking:

```text
What are your skills?
```

In local verification, Claude listed `mina-wiki-skill` in its skill list after installation under `~/.claude/skills/`.

You can invoke it directly as a skill with:

```text
/mina-wiki-skill
```

In local verification, invoking `/mina-wiki-skill` caused Claude to begin the workflow by attempting to run `python3 scripts/wiki_sync_status.py`, then showing its normal approval prompt before executing the command.

The important point is:

- Codex can use this repo as a local skill directly
- Claude can use the same workflow through `CLAUDE.md`, project-local skills, or both

What matters is that both agents receive the same wiki operating rules.

## Recommended Project Integration

If a project uses this workflow seriously, do both:

1. For Codex:
   Install this repo as a local skill and inject the generated wiki section into the project’s `AGENTS.md`.
2. For Claude:
   Inject the generated wiki section into the project’s `CLAUDE.md`.

That keeps both agents aligned on:

- wiki-first memory usage
- `index-first` retrieval
- `sources/` as fallback only
- project-local taxonomy
- project-level git history for wiki changes

## The Core Commands

These are the commands the agents or the user will most often run.

### Configuration and Sync

```bash
python3 scripts/check_paths.py
python3 scripts/raw_git_status.py
python3 scripts/wiki_sync_status.py
python3 scripts/wiki_sync.py --update-sync-marker
```

### Structure and Editing

```bash
python3 scripts/bootstrap_wiki.py
python3 scripts/wiki_index.py
python3 scripts/wiki_ingest.py source.md
python3 scripts/migrate_to_hierarchical.py
```

### Quality

```bash
python3 scripts/wiki_quality_audit.py
python3 scripts/wiki_lint.py
python3 scripts/wiki_enforce_principles.py
python3 scripts/wiki_enforce_principles.py --apply
```

### Query and Benchmark

```bash
python3 scripts/wiki_query.py "What does the example topic do?"
python3 scripts/wiki_benchmark.py --questions questions.json --output-json /tmp/wiki-benchmark.json
```

### Logging and Commits

```bash
python3 scripts/log_operation.py \
  --operation ingest \
  --touched sources/example-source.md topics/example-topic.md \
  --update-sync-marker

python3 scripts/wiki_commit_batch.py --message "Commit wiki batch"
python3 scripts/wiki_git_init.py
```

### Raw Git Initialization

If raw is not yet a git repo:

```bash
python3 scripts/raw_git_init.py
python3 scripts/raw_git_init.py --initial-commit
```

## Lifecycle

The intended lifecycle is:

### 1. Configure

Set `WIKI_RAW_DIR` and `WIKI_DIR`.

### 2. Bootstrap

Create the initial wiki structure with `bootstrap_wiki.py`.

### 3. Sync

Use `wiki_sync_status.py` and `wiki_sync.py` to refresh the wiki when raw changes.

### 4. Editorial Pass

This is where quality comes from.

After sync, the agent should:

- inspect touched `sources/` pages
- inspect the maintained topic pages those sources feed into
- rewrite placeholders and weak summaries
- split or merge pages where needed
- create analyses when multiple sources support a synthesis

A script-only pass is incomplete.

### 5. Query

Normal question-answering should use:

1. root `index.md`
2. section indexes
3. leaf pages
4. `sources/` only if maintained pages are insufficient

This is the `index-first` retrieval model.

### 6. Quality Gates

Run:

```bash
python3 scripts/wiki_index.py
python3 scripts/wiki_quality_audit.py
python3 scripts/wiki_lint.py
python3 scripts/wiki_enforce_principles.py
```

### 7. Benchmark

Use `wiki_benchmark.py` when you need evidence that the wiki structure is actually helping retrieval efficiency.

### 8. Commit

Commit wiki changes through the **parent project repository**.

- `WIKI_RAW_DIR` may have its own git repo
- `WIKI_DIR` must **not** create a nested git repo

Use:

```bash
python3 scripts/wiki_commit_batch.py --message "Update wiki batch"
```

## Git Model

The git model is intentionally asymmetric:

- `WIKI_RAW_DIR` may use its own dedicated git repository
- `WIKI_DIR` should **not** create a nested git repository
- wiki changes should be committed through the parent project repository that contains `WIKI_DIR`

This lets raw freshness stay independent while keeping wiki history inside the project’s normal git history.

## Quality Bar

The maintained wiki is not healthy if:

- the workflow hardcodes a project-specific taxonomy
- maintained pages read like raw mirrors
- `sources/` becomes the default answer path
- placeholders such as `Auto-maintained` remain
- indexes are stale, thin, or empty
- active pages still point into `legacy/`
- wiki updates churn metadata unnecessarily
- wiki history depends on a nested repo instead of the parent project repo

## Testing

Run:

```bash
make test
```

The tests cover:

- config resolution
- raw sync-state detection
- fallback and custom taxonomy behavior
- `index-first` query behavior
- benchmark output and regression gating
- principle enforcement and auto-fix
- migration behavior
- sync cleanup behavior
- parent project git usage for wiki commits
- generated project-injection snippets for `AGENTS.md` and `CLAUDE.md`

## If You Only Remember Three Things

1. Install it as a local skill for Codex, and inject its guidance into project docs for Claude.
2. The wiki is the memory; raw is ingestion input.
3. This is not an Obsidian workflow, and the wiki should commit through the parent project repo, not its own nested git repo.
