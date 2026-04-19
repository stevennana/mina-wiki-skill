#!/usr/bin/env python3
"""Generate reusable command and injection files for Codex and Claude."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from slash_command_catalog import COMMANDS, SlashCommand


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="generated/slash-commands",
        help="Directory where generated command files should be written.",
    )
    return parser.parse_args()


def render_command_markdown(target: str, command: SlashCommand) -> str:
    prompt_intro = (
        "Use this as a stable command-shaped prompt in Codex."
        if target == "codex"
        else "Use this as a stable slash-style prompt in Claude."
    )
    lines = [
        f"# /{command.name}",
        "",
        f"Target: {target}",
        "",
        f"Summary: {command.summary}",
        "",
        "Usage:",
        f"`{command.usage}`",
        "",
        "Prompt contract:",
        prompt_intro,
        "",
        "Behavior:",
    ]
    lines.extend(f"- {step}" for step in command.behavior)
    if command.safety_notes:
        lines.extend(["", "Safety:"])
        lines.extend(f"- {note}" for note in command.safety_notes)
    lines.extend(["", "Examples:"])
    lines.extend(f"- `{example}`" for example in command.examples)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_dir).resolve()
    manifest: dict[str, object] = {"targets": {}, "project_injection": {}}

    for target in ("codex", "claude"):
        target_dir = output_root / target
        target_dir.mkdir(parents=True, exist_ok=True)
        target_commands: list[dict[str, str]] = []
        for command in COMMANDS:
            path = target_dir / f"{command.name}.md"
            path.write_text(render_command_markdown(target, command), encoding="utf-8")
            target_commands.append(
                {
                    "name": command.name,
                    "usage": command.usage,
                    "path": str(path.relative_to(output_root)),
                }
            )
        manifest["targets"][target] = target_commands

    codex_commands = manifest["targets"]["codex"]
    codex_lines = [
        "## Codex Wiki Commands",
        "",
        "This project uses `mina-wiki-skill` for wiki maintenance. For Codex, use the generated command contracts in:",
        "",
        "`generated/slash-commands/codex/`",
        "",
        "Available commands:",
    ]
    codex_lines.extend(f"- `/{item['name']}`" for item in codex_commands)
    codex_lines.extend(["", "Command contract files:"])
    codex_lines.extend(f"- `{item['path']}`" for item in codex_commands)
    codex_lines.extend(
        [
            "",
            "Use these as stable command-shaped prompts in Codex.",
            "They should stay behaviorally aligned with the Claude guidance generated below.",
            "",
        ]
    )
    codex_snippet_path = output_root / "codex-commands-snippet.md"
    codex_snippet_path.write_text("\n".join(codex_lines), encoding="utf-8")
    manifest["project_injection"]["codex_agents_section"] = str(codex_snippet_path.relative_to(output_root))

    agents_lines = [
        "## Wiki Workflow",
        "",
        "This project uses `mina-wiki-skill` for long-lived markdown knowledge management.",
        "",
        "- `WIKI_DIR` is the maintained project memory and should be consulted before re-deriving answers from raw material.",
        "- `WIKI_RAW_DIR` is ingestion input and should not be treated as the default reading surface.",
        "- Query the wiki with an `index-first` approach: root `index.md` -> section indexes -> leaf pages.",
        "- Use `sources/` only as fallback when maintained pages are insufficient.",
        "- Keep taxonomy project-local via `.mina-wiki.json` or `WIKI_DIR/.mina-wiki/taxonomy.json`; do not hardcode domain taxonomy into shared helpers.",
        "- Raw may use its own dedicated git repository.",
        "- The wiki must not create a nested git repository; commit wiki changes through the parent project repository that contains `WIKI_DIR`.",
        "- After meaningful wiki changes, rebuild indexes and run lint / quality / principle checks.",
        "",
        "Suggested commands:",
        "",
        "```bash",
        "python3 scripts/wiki_sync_status.py",
        "python3 scripts/wiki_sync.py --update-sync-marker",
        "python3 scripts/wiki_index.py",
        "python3 scripts/wiki_quality_audit.py",
        "python3 scripts/wiki_lint.py",
        "python3 scripts/wiki_enforce_principles.py",
        "```",
        "",
    ]
    agents_snippet_path = output_root / "agents-wiki-snippet.md"
    agents_snippet_path.write_text("\n".join(agents_lines), encoding="utf-8")
    manifest["project_injection"]["agents_wiki_section"] = str(agents_snippet_path.relative_to(output_root))

    claude_lines = [
        "## Wiki Memory Rules",
        "",
        "This project uses `mina-wiki-skill` for long-lived markdown knowledge management across Codex and Claude sessions.",
        "",
        "- Use the maintained wiki as the first source of truth for project questions.",
        "- Start from `index.md`, then follow section indexes and leaf pages before reading raw material.",
        "- Treat `sources/` as fallback evidence, not the primary surface.",
        "- When raw changed, check sync status first and ask before running a full wiki sync.",
        "- When updating the wiki, preserve stable structure, avoid placeholder text, and prefer stronger maintained pages over raw mirrors.",
        "- Keep wiki history inside the parent project repository. Do not run `git init` inside `WIKI_DIR`.",
        "- If the project defines a taxonomy, keep it in config, not in shared skill code.",
        "",
        "Suggested commands:",
        "",
        "```bash",
        "python3 scripts/wiki_sync_status.py",
        "python3 scripts/wiki_sync.py --update-sync-marker",
        "python3 scripts/wiki_index.py",
        "python3 scripts/wiki_quality_audit.py",
        "python3 scripts/wiki_lint.py",
        "python3 scripts/wiki_enforce_principles.py",
        "python3 scripts/wiki_benchmark.py --questions /path/to/questions.json --output-json /tmp/wiki-benchmark.json",
        "```",
        "",
    ]
    claude_snippet_path = output_root / "claude-wiki-snippet.md"
    claude_snippet_path.write_text("\n".join(claude_lines), encoding="utf-8")
    manifest["project_injection"]["claude_wiki_section"] = str(claude_snippet_path.relative_to(output_root))

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output_dir": str(output_root), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
