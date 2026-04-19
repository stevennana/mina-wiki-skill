from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import wiki_common
from scripts.slash_command_catalog import COMMANDS


REPO_ROOT = Path(__file__).resolve().parents[1]


def git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class MinaWikiSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.raw_dir = self.root / "raw"
        self.wiki_dir = self.root / "wiki"
        self.config_path = self.root / ".mina-wiki.json"
        self.raw_dir.mkdir()
        self.wiki_dir.mkdir()
        git(self.raw_dir, "init")
        git(self.raw_dir, "config", "user.name", "Test User")
        git(self.raw_dir, "config", "user.email", "test@example.com")
        (self.raw_dir / "source.md").write_text("# Example Topic\n\nThe example topic coordinates work.\n", encoding="utf-8")
        git(self.raw_dir, "add", "source.md")
        git(self.raw_dir, "commit", "-m", "init")
        self.env_backup = os.environ.copy()
        os.environ["WIKI_RAW_DIR"] = str(self.raw_dir)
        os.environ["WIKI_DIR"] = str(self.wiki_dir)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.env_backup)
        self.temp_dir.cleanup()

    def run_script(self, relative: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(REPO_ROOT / relative), *args],
            cwd=REPO_ROOT,
            check=check,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

    def write_config(self, payload: dict[str, object]) -> None:
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")
        os.environ["MINA_WIKI_CONFIG"] = str(self.config_path)

    def test_env_resolution_wins(self) -> None:
        self.write_config({"raw_dir": "/tmp/ignored-raw", "wiki_dir": "/tmp/ignored-wiki"})
        paths = wiki_common.resolve_paths()
        self.assertEqual(paths.raw_dir, self.raw_dir.resolve())
        self.assertEqual(paths.wiki_dir, self.wiki_dir.resolve())

    def test_sync_needed_without_metadata(self) -> None:
        status = wiki_common.compute_sync_status(wiki_common.resolve_paths())
        self.assertTrue(status["needs_sync"])
        self.assertIn("No sync metadata found in wiki.", status["reasons"])

    def test_bootstrap_wiki_creates_fallback_hierarchy(self) -> None:
        completed = self.run_script("scripts/bootstrap_wiki.py", check=False)
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue((self.wiki_dir / "index.md").exists())
        self.assertTrue((self.wiki_dir / "topics" / "index.md").exists())
        self.assertTrue((self.wiki_dir / "sources" / "index.md").exists())
        self.assertIn("topics/index.md", payload["created"])

    def test_custom_taxonomy_is_used_for_bootstrap_and_ingest(self) -> None:
        self.write_config(
            {
                "taxonomy": {
                    "root_sections": ["sections"],
                    "children": {"sections": ["example-subsection", "reference"]},
                    "section_descriptions": {"sections/example-subsection": "Example subsection."},
                    "default_destination": "sections/example-subsection",
                    "routing_rules": [{"pattern": "example topic", "destination": "sections/example-subsection", "match": "any"}],
                }
            }
        )
        completed = self.run_script("scripts/wiki_ingest.py", "source.md", check=False)
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue((self.wiki_dir / "sections" / "example-subsection" / "example-topic.md").exists())
        self.assertTrue((self.wiki_dir / ".mina-wiki" / "taxonomy.json").exists())

    def test_wiki_index_builds_indexes_for_custom_taxonomy(self) -> None:
        self.write_config(
            {
                "taxonomy": {
                    "root_sections": ["sections"],
                    "children": {"sections": ["example-subsection"]},
                    "default_destination": "sections/example-subsection",
                }
            }
        )
        self.run_script("scripts/wiki_ingest.py", "source.md")
        completed = self.run_script("scripts/wiki_index.py", check=False)
        self.assertEqual(completed.returncode, 0)
        root_index = (self.wiki_dir / "index.md").read_text(encoding="utf-8")
        subsection_index = (self.wiki_dir / "sections" / "example-subsection" / "index.md").read_text(encoding="utf-8")
        self.assertIn("[[sections/index]]", root_index)
        self.assertIn("[[sections/example-subsection/example-topic]]", subsection_index)

    def test_wiki_query_can_save_analysis(self) -> None:
        self.run_script("scripts/wiki_ingest.py", "source.md")
        completed = self.run_script(
            "scripts/wiki_query.py",
            "What does the example topic do?",
            "--save-to",
            "example-topic-answer",
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue((self.wiki_dir / "analyses" / "example-topic-answer.md").exists())
        self.assertTrue(payload["citations"])

    def test_sync_cleanup_preserves_last_reviewed_on_automatic_source_removal(self) -> None:
        taxonomy = wiki_common.resolve_taxonomy(wiki_common.resolve_paths())
        wiki_common.ensure_wiki_structure(self.wiki_dir, taxonomy)
        source_path = self.wiki_dir / "sources" / "source.md"
        wiki_common.write_wiki_page(
            source_path,
            {"type": "source", "title": "Source", "last_reviewed": "2026-04-19"},
            "## Summary\n\nRaw source summary.\n",
        )
        maintained_path = self.wiki_dir / "topics" / "example-topic.md"
        wiki_common.write_wiki_page(
            maintained_path,
            {
                "type": "concept",
                "title": "Example Topic",
                "last_reviewed": "2025-01-01",
                "sources": ["sources/source", "sources/other"],
            },
            "## Summary\n\nExample topic page.\n\n## Source Coverage\n\n- [[sources/source]]\n- [[sources/other]]\n",
        )
        wiki_common.write_source_map(self.wiki_dir, {"source.md": "sources/source"})
        snapshot = wiki_common.git_snapshot(self.raw_dir)
        wiki_common.write_sync_metadata(self.wiki_dir, snapshot, "sync")

        (self.raw_dir / "source.md").unlink()
        git(self.raw_dir, "rm", "source.md")
        git(self.raw_dir, "commit", "-m", "remove source")

        completed = self.run_script("scripts/wiki_sync.py", "--update-sync-marker", check=False)
        self.assertEqual(completed.returncode, 0)
        metadata, body = wiki_common.read_wiki_page(maintained_path)
        self.assertEqual(metadata["last_reviewed"], "2025-01-01")
        self.assertNotIn("[[sources/source]]", body)

    def test_migrate_to_hierarchical_uses_configured_destination_and_archives_flat_pages(self) -> None:
        self.write_config(
            {
                "taxonomy": {
                    "root_sections": ["sections"],
                    "children": {"sections": ["example-subsection"]},
                    "default_destination": "sections/example-subsection",
                }
            }
        )
        flat_dir = self.wiki_dir / "concepts"
        flat_dir.mkdir(exist_ok=True)
        wiki_common.write_wiki_page(
            flat_dir / "example-topic.md",
            {"type": "concept", "title": "Example Topic", "last_reviewed": "2026-04-19"},
            "## Summary\n\nFlat example topic page.\n",
        )

        completed = self.run_script("scripts/migrate_to_hierarchical.py", check=False)
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue((self.wiki_dir / "sections" / "example-subsection" / "example-topic.md").exists())
        self.assertTrue((self.wiki_dir / "legacy" / "flat" / "concepts" / "example-topic.md").exists())

    def test_quality_audit_flags_placeholder_pages(self) -> None:
        taxonomy = wiki_common.resolve_taxonomy(wiki_common.resolve_paths())
        wiki_common.ensure_wiki_structure(self.wiki_dir, taxonomy)
        wiki_common.write_wiki_page(
            self.wiki_dir / "topics" / "draft.md",
            {"type": "concept", "title": "Draft", "last_reviewed": "2026-04-19"},
            "## Summary\n\nAuto-maintained draft.\n",
        )
        completed = self.run_script("scripts/wiki_quality_audit.py", check=False)
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertIn("topics/draft.md", payload["placeholder_pages"])

    def test_slash_commands_reference_generic_paths(self) -> None:
        sync = next(command for command in COMMANDS if command.name == "wiki-sync")
        self.assertIn("section indexes", " ".join(sync.behavior))
        add_source = next(command for command in COMMANDS if command.name == "wiki-add-source")
        self.assertIn("configured taxonomy", " ".join(add_source.behavior))


if __name__ == "__main__":
    unittest.main()
