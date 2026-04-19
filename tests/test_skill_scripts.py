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
        git(self.root, "init")
        git(self.root, "config", "user.name", "Test User")
        git(self.root, "config", "user.email", "test@example.com")
        (self.root / ".gitignore").write_text("raw/\n", encoding="utf-8")
        git(self.root, "add", ".gitignore")
        git(self.root, "commit", "-m", "init project")
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
        self.assertEqual(wiki_common.git_toplevel(self.wiki_dir), self.root.resolve())

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
        wiki_common.write_wiki_page(
            self.wiki_dir / "topics" / "secondary-topic.md",
            {"type": "concept", "title": "Secondary Topic", "last_reviewed": "2026-04-19"},
            "## Summary\n\nA less relevant topic.\n",
        )
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
        self.assertIn(payload["mode"], {"index_first", "sources_fallback", "fallback_full_scan"})
        self.assertIn("matched_pages", payload)
        self.assertIn("top_score", payload)
        self.assertTrue(any("example-topic" in ref for ref in payload["citations"]))
        self.assertFalse(any("secondary-topic" == Path(ref).name for ref in payload["citations"]))

    def test_wiki_benchmark_outputs_summary(self) -> None:
        self.run_script("scripts/wiki_ingest.py", "source.md")
        questions_path = self.root / "questions.json"
        questions_path.write_text(json.dumps([{"id": "q1", "question": "What does the example topic do?"}]), encoding="utf-8")
        output_json = self.root / "benchmark.json"
        output_md = self.root / "benchmark.md"
        completed = self.run_script(
            "scripts/wiki_benchmark.py",
            "--questions",
            str(questions_path),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--write-baseline",
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(output_json.exists())
        self.assertTrue(output_md.exists())
        benchmark_payload = json.loads(output_json.read_text(encoding="utf-8"))
        self.assertEqual(benchmark_payload["summary"]["question_count"], 1)
        self.assertTrue((self.wiki_dir / ".mina-wiki" / "benchmarks" / "baseline.json").exists())
        completed_compare = self.run_script(
            "scripts/wiki_benchmark.py",
            "--questions",
            str(questions_path),
            "--output-json",
            str(self.root / "benchmark-2.json"),
            check=False,
        )
        self.assertEqual(completed_compare.returncode, 0)
        compare_payload = json.loads((self.root / "benchmark-2.json").read_text(encoding="utf-8"))
        self.assertIn("comparison", compare_payload)
        completed_regression = self.run_script(
            "scripts/wiki_benchmark.py",
            "--questions",
            str(questions_path),
            "--output-json",
            str(self.root / "benchmark-3.json"),
            "--compare-json",
            str(output_json),
            "--fail-on-regression",
            "--max-elapsed-regression-ms",
            "-1",
            check=False,
        )
        self.assertEqual(completed_regression.returncode, 2)

    def test_wiki_git_init_reports_parent_project_repo(self) -> None:
        completed = self.run_script("scripts/wiki_git_init.py", check=False)
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["uses_project_level_git"])
        self.assertEqual(Path(payload["repo_root"]), self.root.resolve())

    def test_wiki_commit_batch_uses_parent_project_repo(self) -> None:
        taxonomy = wiki_common.resolve_taxonomy(wiki_common.resolve_paths())
        wiki_common.ensure_wiki_structure(self.wiki_dir, taxonomy)
        (self.root / "unrelated.txt").write_text("leave me unstaged\n", encoding="utf-8")
        wiki_common.write_wiki_page(
            self.wiki_dir / "topics" / "committed-topic.md",
            {"type": "concept", "title": "Committed Topic", "last_reviewed": "2026-04-19"},
            "## Summary\n\nCommitted topic body.\n",
        )
        completed = self.run_script(
            "scripts/wiki_commit_batch.py",
            "--message",
            "Commit wiki batch",
            "--paths",
            "topics/committed-topic.md",
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["committed"])
        self.assertEqual(Path(payload["repo_root"]), self.root.resolve())
        last_message = git(self.root, "log", "-1", "--pretty=%s")
        self.assertEqual(last_message, "Commit wiki batch")
        status_after = git(self.root, "status", "--short")
        self.assertIn("?? unrelated.txt", status_after)

    def test_wiki_enforce_principles_detects_issues(self) -> None:
        taxonomy = wiki_common.resolve_taxonomy(wiki_common.resolve_paths())
        wiki_common.ensure_wiki_structure(self.wiki_dir, taxonomy)
        wiki_common.write_wiki_page(
            self.wiki_dir / "topics" / "index.md",
            {"type": "index", "title": "Topics", "last_reviewed": "2026-04-19"},
            "## Summary\n\nAuto-maintained topics index.\n",
        )
        wiki_common.write_wiki_page(
            self.wiki_dir / "topics" / "orphan.md",
            {"type": "concept", "title": "Orphan", "last_reviewed": "2026-04-19", "sources": ["sources/missing"]},
            "## Summary\n\nAuto-maintained orphan page.\n\n- [[legacy/flat/concepts/old-topic]]\n",
        )
        completed = self.run_script("scripts/wiki_enforce_principles.py", check=False)
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["auto_fixable"])
        self.assertTrue(payload["violations"] or payload["manual_review"])
        completed_apply = self.run_script("scripts/wiki_enforce_principles.py", "--apply", check=False)
        self.assertEqual(completed_apply.returncode, 2)
        applied_payload = json.loads(completed_apply.stdout)
        self.assertTrue(applied_payload["fixed_pages"])
        _metadata, fixed_body = wiki_common.read_wiki_page(self.wiki_dir / "topics" / "orphan.md")
        self.assertIn("## Source Coverage", fixed_body)
        self.assertNotIn("[[legacy/flat/concepts/old-topic]]", fixed_body)
        _index_meta, fixed_index_body = wiki_common.read_wiki_page(self.wiki_dir / "topics" / "index.md")
        self.assertNotIn("Auto-maintained", fixed_index_body)

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
        benchmark = next(command for command in COMMANDS if command.name == "wiki-benchmark")
        self.assertIn("fallback usage", " ".join(benchmark.behavior))

    def test_generate_slash_commands_writes_project_injection_snippets(self) -> None:
        output_dir = self.root / "generated"
        completed = self.run_script(
            "scripts/generate_slash_commands.py",
            "--output-dir",
            str(output_dir),
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue((output_dir / "agents-wiki-snippet.md").exists())
        self.assertTrue((output_dir / "claude-wiki-snippet.md").exists())
        self.assertIn("agents_wiki_section", manifest["project_injection"])
        self.assertIn("claude_wiki_section", manifest["project_injection"])


if __name__ == "__main__":
    unittest.main()
