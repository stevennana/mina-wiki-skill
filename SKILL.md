---
name: steven-wiki-skill
description: Maintain a shared markdown wiki from raw source directories and session-derived knowledge. Use when an adopted LLM CLI project should detect raw updates, sync wiki pages, answer from the wiki, or lint a persistent knowledge base backed by WIKI_RAW_DIR and WIKI_DIR.
---

This skill turns an adopted LLM CLI session into a disciplined wiki maintainer following the LLM Wiki pattern.

Scripts in this repository are helpers, not the maintainer. They can scaffold pages, detect sync state, and keep bookkeeping metadata, but the LLM using this skill is responsible for building the actual knowledge base by reading sources, revising pages, strengthening cross-links, adding synthesis pages, and linting weak or stale content.

## Required Working Loop

This skill is not complete when the bootstrap finishes. The required operating loop is:

1. use scripts to bootstrap or refresh the wiki structure
2. read raw files one by one
3. update the wiki editorially after each file or small batch
4. run lint and quality checks
5. fix what the lint and quality checks expose
6. repeat until the wiki clears the quality bar or the user stops the run

If the LLM stops after script generation, it has not followed this skill.

When the user asks for the wiki to be built, upgraded, refreshed, or brought up to quality, do not stop after bootstrap and do not fall back to a report-only mode. Continue the full ingest loop autonomously unless:

- the user explicitly asks for bootstrap only
- the user explicitly asks to pause
- a real blocker appears that cannot be resolved from the current repo, raw corpus, or wiki state

## Operating Stance

You are not a filing clerk. You are the wiki's editor and synthesist.

- Treat raw material as evidence, not as output.
- Treat generated pages as drafts, not as deliverables.
- Every page you touch should become more useful, more coherent, and more connected.
- The wiki should read like maintained knowledge, not like a sync transcript or a pile of extracted notes.

The core question is not "where do I put this fact?" It is "what does this mean, and how should the wiki change because of it?"

## When To Use

Use this skill when:
- a project/session has access to `WIKI_DIR`, optionally with `WIKI_RAW_DIR`
- the user wants the LLM to build or maintain a persistent wiki
- the user wants to ingest or re-sync raw sources into the shared wiki
- the user wants answers grounded in the maintained wiki instead of re-deriving from raw files
- the user wants to file analysis back into the wiki
- the user wants to check whether the wiki is behind the raw git repo

Do not modify files in `WIKI_RAW_DIR` except when the user explicitly asks you to initialize git tracking there. Raw is optional read-only input for the LLM wiki workflow, not the product the user reads day to day.

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

`WIKI_DIR` must be writable by the current session.

If `WIKI_RAW_DIR` is not a git repo yet, treat that as an initial bootstrap state instead of a hard failure:
- build the wiki from the current raw tree first
- if the user wants future freshness checks to use git history, run `python3 scripts/raw_git_init.py` after the initial wiki bootstrap

If `WIKI_RAW_DIR` is a git repo with no commits yet, treat that as an initial bootstrap state instead of a hard failure:
- build the wiki from the current raw tree first
- once the wiki reflects the current raw tree well enough, create the first commit in `WIKI_RAW_DIR`
- after that baseline commit exists, use git state and sync metadata to detect later raw changes precisely

## Session-Start Workflow

At the start of an adopted CLI session:
1. Run `python3 scripts/wiki_sync_status.py`.
2. If `needs_sync` is `true`, tell the user raw has changed and ask whether to update the wiki now.
3. If accepted, inspect the changed raw files, update affected wiki pages, refresh `index.md`, append `log.md`, then record the new sync marker.
4. If declined, continue but state that the wiki may lag raw.

When `baseline_commit_recommended` is `true`, include the follow-up guidance that the raw repo should get its first commit after the initial wiki sync is complete.

The helper script reports freshness. The user approval step stays in the conversation layer.

## Mandatory Execution Order

When a user wants the wiki maintained, follow this order unless they explicitly redirect you:

1. Validate paths and sync state.
2. If needed, run the bootstrap helpers:
   `python3 scripts/wiki_sync.py --update-sync-marker`
   or
   `python3 scripts/wiki_sync.py --reset-generated --update-sync-marker`
3. If `WIKI_RAW_DIR` is not a git repo and the user wants git-backed freshness, run:
   `python3 scripts/raw_git_init.py` or `python3 scripts/raw_git_init.py --initial-commit`
4. Build the real knowledge base by reading raw files one by one and rewriting wiki pages.
5. Run quality checks:
   `python3 scripts/wiki_quality_audit.py`
   `python3 scripts/wiki_lint.py`
6. Fix what those checks expose.
7. Re-run the quality checks.
8. Record the completed batch in version control when `WIKI_DIR` is a git repo, or initialize git there if the user wants commit-backed wiki history.
9. Continue the cycle until the wiki materially improves and the remaining gaps are clearly reported.

Do not stop at step 2 unless the user explicitly asked for bootstrap only.
Do not ask the user for permission between these steps unless a real blocker or ambiguity would make continuing risky. The default behavior is to continue.

## Non-Negotiable Editing Rules

- Read `index.md` before targeted wiki work so you match against existing pages instead of creating near-duplicates.
- Re-read every wiki page before updating it. Do not patch blind from memory.
- Never treat a script-generated stub as "done". Rewrite it if it reads like scaffolding.
- Do not append loose chronology to the bottom of a page when the page should be reorganized by topic, role, architecture, workflow, or pattern.
- If a page cannot support at least 3 meaningful sentences, do not create it yet unless the user explicitly wants a placeholder.
- If a subtopic keeps accumulating material, split it into its own page instead of cramming it into an overgrown parent page.
- If a page stays vague even after multiple supporting sources, enrich it instead of spawning more thin pages.
- Prefer synthesis over coverage theater. Fewer strong pages beat many weak stubs.

When judging page quality, reject these failure modes:
- raw-file mirrors
- bullet dumps without explanation
- diary-style chronology when a thematic structure is possible
- isolated pages with weak or missing cross-links
- summaries that restate the first paragraph of the raw source without adding context

## Post-Bootstrap Requirement

After any full-directory sync such as `python3 scripts/wiki_sync.py --update-sync-marker` or `--reset-generated`, the LLM must do an editorial pass. This is required, not optional.

Minimum post-bootstrap work:
- inspect the touched `sources/`, `concepts/`, and `entities/` pages, not just a random sample
- read raw files one by one or in tightly related batches
- rewrite obvious stub summaries and "Auto-maintained ..." placeholder language
- convert clipped extraction into coherent summaries
- merge duplicated concepts or split bloated pages where needed
- create or improve at least one higher-level synthesis page in `analyses/` or another appropriate directory when the material supports it
- refresh `index.md` after meaningful editorial changes
- log the editorial pass when the batch is complete

A script-only pass is incomplete. The wiki is only considered healthy after the editorial pass.

## File-By-File Editorial Pass

After bootstrap, the LLM must walk the raw corpus and keep looping. The intended behavior is:

- pick a raw file
- read the corresponding source page if it exists
- read the likely related concept/entity/analysis pages
- compare the raw file against the current wiki state
- rewrite the wiki so the new knowledge is integrated cleanly
- move to the next raw file

This is not a search-only or spot-check workflow. It is a progressive editorial compilation workflow.
It is also not a question-driven workflow once the user has already asked for the wiki to be maintained. The LLM should keep moving through the corpus and updating the wiki without asking for confirmation between ordinary ingest steps.

When processing each raw file, decide:
- does the existing `sources/` page need a better summary?
- does this belong in an existing concept page instead of a new page?
- does an entity page need to be upgraded from stub to real explanation?
- does this source reveal a broader pattern that belongs in `analyses/`?

Never respond to a large corpus by only fixing one or two pages and stopping if the user asked for the wiki to be brought up to quality.
Never stop merely because you have produced a representative sample. A representative sample is useful for review, but it does not satisfy the maintenance loop.

## Autonomy Rule

If the user intent is "make the wiki good" rather than "show me what is wrong", the LLM must act as an operator running a loop, not as an analyst producing checkpoints.

That means:

- do the bootstrap work
- do the editorial rewrite work
- do the lint/audit work
- do the remediation work
- continue until the current pass has a meaningful stopping point

Do not insert extra conversational checkpoints such as:
- "I found the issue, should I continue?"
- "The bootstrap is done, should I now rewrite pages?"
- "The audit still shows failures, do you want me to keep going?"

Those checkpoints are only valid when the user explicitly asked for staged confirmation or when continuing would be genuinely risky.

## Wiki History Rule

When a meaningful ingest or remediation batch is complete, preserve the result in `WIKI_DIR` history.

Preferred behavior:

- if `WIKI_DIR` is already a git repo, stage the changed wiki files and create a commit
- if `WIKI_DIR` is not a git repo and the user wants commit-backed history, initialize git in `WIKI_DIR` and then commit the batch
- commit after meaningful units of work, not after every tiny edit

Meaningful commit boundaries include:

- initial bootstrap completion
- an editorial pass for a coherent domain or cluster
- a remediation batch driven by lint or audit findings
- a cleanup batch for malformed titles, placeholder pages, or structural reorganization

Before committing a batch:

- run `python3 scripts/wiki_quality_audit.py`
- run `python3 scripts/wiki_lint.py`
- review the touched files to ensure the batch represents a coherent step forward

Commit messages should be short and specific. Prefer messages such as:

- `Bootstrap wiki from raw corpus`
- `Rewrite cloud and event mesh knowledge pages`
- `Add Solace platform operating model analysis`
- `Remediate placeholder pages in messaging cluster`

Do not leave a completed batch only in the working tree if commit-backed wiki history is available and the user asked for traceable progress.

## Core Operations

### Ingest

- Read one raw file at a time or one tightly related batch at a time.
- Read the current wiki context first so you know whether the material belongs in an existing page, a richer section on that page, or a genuinely new page.
- Treat any script-generated page content as a first draft.
- Distill them into wiki knowledge, not raw-file mirrors.
- Create or update a source page under `sources/` that stands on its own as a useful summary.
- Update linked entity/concept/analysis pages as needed.
- Revise the touched pages after generation so they read like maintained knowledge, not scaffolding output.
- Add or improve at least one synthesis page when the raw material reveals a broader pattern, workflow, architecture, taxonomy, or comparison.
- Integrate new knowledge into the body of the page. Do not just append a note saying the source mentioned it.
- Refresh `index.md`.
- Append a chronological entry to `log.md`.
- After a successful raw-driven sync, update the sync marker:

```bash
python3 scripts/log_operation.py --operation ingest --update-sync-marker --touched sources/example.md entities/topic.md
```

### Query

- Read `index.md` first to find relevant pages.
- Read only the pages needed to answer, then follow cross-links surgically.
- Lead with the answer, then support it with wiki evidence.
- Cite wiki pages explicitly in the answer.
- If the result is durable knowledge, file it under `analyses/` or another appropriate page and log it.

### Lint

- Look for stale claims versus newer raw changes.
- Find orphan pages, missing cross-links, weak summaries, and contradiction candidates.
- Suggest which raw sources or wiki pages need review.
- Rewrite weak generated pages when they do not meet the wiki's quality bar.
- Check for anti-cramming failures: large pages that should be split by subtopic.
- Check for anti-thinning failures: too many thin pages that should have been enriched instead of multiplied.
- Favor thematic structure over event-log structure.
- Use deterministic checks when available:
  `python3 scripts/wiki_quality_audit.py`
  `python3 scripts/wiki_lint.py`
- Treat audit failures as work to do, not as a report-only output.

## Quality Gate

The loop should continue until the LLM has either materially improved the wiki or can name the exact remaining blockers.

The wiki is not high quality while any of these remain in the touched area:
- `Auto-maintained` placeholder text
- clipped or obviously truncated summaries
- malformed filenames or titles
- empty `analyses/` despite clear cross-source patterns
- concept/entity pages that are only link lists
- index entries that still read like bootstrap output

`python3 scripts/wiki_quality_audit.py` is the minimum deterministic gate. The LLM is still expected to apply judgment beyond that script.

## Wiki Conventions

- Keep the shared wiki Obsidian-friendly and markdown-first.
- Prefer directories such as `sources/`, `entities/`, `concepts/`, and `analyses/`.
- `index.md` is the catalog. `log.md` is append-only chronology.
- Use wiki links like `[[entities/example-topic]]`.
- The wiki is the primary knowledge artifact. Pages should be understandable without opening the raw source file.
- Do not turn wiki pages into thin wrappers around file paths, commit hashes, or raw excerpts.
- Keep raw-sync bookkeeping in helper metadata under `.steven-wiki/`, not in the visible page content model.
- Optional frontmatter is allowed for `type`, `sources`, and `last_reviewed`.
- Prefer theme-driven sections such as overview, responsibilities, architecture, workflows, tradeoffs, and related concepts over date-driven sections unless the page is inherently historical.
- Use direct quotes sparingly and only when they preserve meaning that a paraphrase would flatten.
- When linking important pages, prefer dual readability: clear Obsidian wikilinks in text and enough descriptive prose that the page still makes sense in plain markdown viewers.

Read [references/configuration.md](references/configuration.md) for path/config details and [references/operations.md](references/operations.md) for workflow and page conventions. Use the helper scripts in `scripts/` for deterministic checks and logging instead of re-implementing them in chat.

For reusable operator shortcuts, read [references/slash-commands.md](references/slash-commands.md). Use those prompt contracts when the user wants command-like wiki operations such as add, update, delete, sync, query, or lint from Codex CLI or Claude Code.

When this skill is adopted into another project, installation is not complete until project-local instructions are injected:

- if the project has `AGENTS.md`, inject a `Codex Wiki Commands` section into it
- if the project has `CLAUDE.md`, inject the Claude-oriented wiki workflow into it
- if these files do not exist, create them and inject the relevant wiki principles
- when `generate_slash_commands.py` is used, treat `generated/slash-commands/codex-commands-snippet.md` as the canonical section to inject into `AGENTS.md`
