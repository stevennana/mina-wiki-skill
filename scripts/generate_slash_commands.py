#!/usr/bin/env python3
"""Generate reusable slash-command prompt files for Codex and Claude."""

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
        "Use this as a stable command-shaped prompt in Codex CLI."
        if target == "codex"
        else "Use this as a stable slash-style prompt in Claude Code."
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
            "Use these as stable command-shaped prompts in Codex. They are not native Claude-style slash commands,",
            "but they define the exact behavior Codex should follow for project wiki operations.",
            "",
        ]
    )
    codex_snippet_path = output_root / "codex-commands-snippet.md"
    codex_snippet_path.write_text("\n".join(codex_lines), encoding="utf-8")
    manifest["project_injection"]["codex_agents_section"] = str(codex_snippet_path.relative_to(output_root))

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output_dir": str(output_root), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
