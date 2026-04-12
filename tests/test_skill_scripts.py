from __future__ import annotations

import json
import os
import shutil
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


class StevenWikiSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.raw_dir = self.root / "raw"
        self.wiki_dir = self.root / "wiki"
        self.raw_dir.mkdir()
        self.wiki_dir.mkdir()
        git(self.raw_dir, "init")
        git(self.raw_dir, "config", "user.name", "Test User")
        git(self.raw_dir, "config", "user.email", "test@example.com")
        (self.raw_dir / "source.md").write_text("hello\n", encoding="utf-8")
        git(self.raw_dir, "add", "source.md")
        git(self.raw_dir, "commit", "-m", "init")
        self.env_backup = os.environ.copy()
        os.environ["WIKI_RAW_DIR"] = str(self.raw_dir)
        os.environ["WIKI_DIR"] = str(self.wiki_dir)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.env_backup)
        self.temp_dir.cleanup()

    def test_env_resolution_wins(self) -> None:
        config = self.root / ".steven-wiki.json"
        config.write_text(
            json.dumps({"raw_dir": "/tmp/ignored-raw", "wiki_dir": "/tmp/ignored-wiki"}),
            encoding="utf-8",
        )
        os.environ["STEVEN_WIKI_CONFIG"] = str(config)
        paths = wiki_common.resolve_paths()
        self.assertEqual(paths.raw_dir, self.raw_dir.resolve())
        self.assertEqual(paths.wiki_dir, self.wiki_dir.resolve())

    def test_project_local_config_is_discovered(self) -> None:
        os.environ.pop("WIKI_RAW_DIR", None)
        os.environ.pop("WIKI_DIR", None)
        nested = self.root / "project" / "notes"
        nested.mkdir(parents=True)
        config = self.root / "project" / ".steven-wiki.json"
        config.write_text(
            json.dumps({"raw_dir": str(self.raw_dir), "wiki_dir": str(self.wiki_dir)}),
            encoding="utf-8",
        )
        paths = wiki_common.resolve_paths(nested)
        self.assertEqual(paths.raw_dir, self.raw_dir.resolve())
        self.assertEqual(paths.wiki_dir, self.wiki_dir.resolve())
        self.assertEqual(paths.config_path, config.resolve())

    def test_sync_needed_without_metadata(self) -> None:
        status = wiki_common.compute_sync_status(wiki_common.resolve_paths())
        self.assertTrue(status["needs_sync"])
        self.assertIn("No sync metadata found in wiki.", status["reasons"])
        self.assertFalse(status["baseline_commit_recommended"])

    def test_sync_clears_after_marker_written(self) -> None:
        paths = wiki_common.resolve_paths()
        snapshot = wiki_common.git_snapshot(paths.raw_dir)
        wiki_common.ensure_wiki_structure(paths.wiki_dir)
        wiki_common.write_sync_metadata(paths.wiki_dir, snapshot, "ingest")
        status = wiki_common.compute_sync_status(paths)
        self.assertFalse(status["needs_sync"])

    def test_dirty_raw_requires_sync(self) -> None:
        paths = wiki_common.resolve_paths()
        snapshot = wiki_common.git_snapshot(paths.raw_dir)
        wiki_common.ensure_wiki_structure(paths.wiki_dir)
        wiki_common.write_sync_metadata(paths.wiki_dir, snapshot, "ingest")
        (self.raw_dir / "source.md").write_text("changed\n", encoding="utf-8")
        status = wiki_common.compute_sync_status(paths)
        self.assertTrue(status["needs_sync"])
        self.assertIn("Raw repository has uncommitted changes.", status["reasons"])

    def test_log_operation_script_updates_files(self) -> None:
        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "log_operation.py"),
                "--operation",
                "ingest",
                "--touched",
                "sources/source.md",
                "entities/topic.md",
                "--update-sync-marker",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue((self.wiki_dir / "log.md").exists())
        self.assertTrue((self.wiki_dir / ".steven-wiki" / "last_sync.json").exists())

    def test_check_paths_script_reports_success(self) -> None:
        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "check_paths.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(Path(payload["raw_dir"]), self.raw_dir.resolve())
        self.assertEqual(Path(payload["wiki_dir"]), self.wiki_dir.resolve())

    def test_raw_git_status_script_reports_head(self) -> None:
        expected_branch = git(self.raw_dir, "rev-parse", "--abbrev-ref", "HEAD")
        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "raw_git_status.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["git"]["branch"], expected_branch)
        self.assertFalse(payload["git"]["dirty"])
        self.assertEqual(payload["git"]["changed_files"], [])

    def test_git_snapshot_handles_unborn_head(self) -> None:
        fresh_root = self.root / "fresh"
        fresh_root.mkdir()
        git(fresh_root, "init")
        git(fresh_root, "config", "user.name", "Test User")
        git(fresh_root, "config", "user.email", "test@example.com")
        (fresh_root / "draft.md").write_text("draft\n", encoding="utf-8")
        expected_branch = git(fresh_root, "symbolic-ref", "--short", "HEAD")

        snapshot = wiki_common.git_snapshot(fresh_root)

        self.assertEqual(snapshot["branch"], expected_branch)
        self.assertIsNone(snapshot["head"])
        self.assertEqual(snapshot["short_head"], "unborn")
        self.assertFalse(snapshot["has_commits"])
        self.assertTrue(snapshot["dirty"])
        self.assertEqual(snapshot["changed_files"], ["draft.md"])

    def test_compute_sync_status_recommends_baseline_commit_for_unborn_repo(self) -> None:
        fresh_root = self.root / "fresh-sync"
        fresh_root.mkdir()
        git(fresh_root, "init")
        git(fresh_root, "config", "user.name", "Test User")
        git(fresh_root, "config", "user.email", "test@example.com")
        (fresh_root / "draft.md").write_text("draft\n", encoding="utf-8")

        paths = wiki_common.ResolvedPaths(
            raw_dir=fresh_root.resolve(),
            wiki_dir=self.wiki_dir.resolve(),
            config_path=None,
            source="test",
        )

        status = wiki_common.compute_sync_status(paths)

        self.assertTrue(status["needs_sync"])
        self.assertTrue(status["baseline_commit_recommended"])
        self.assertTrue(status["follow_up_actions"])
        self.assertIn("no baseline commit yet", " ".join(status["reasons"]).lower())

    def test_git_snapshot_handles_non_git_raw_directory(self) -> None:
        plain_root = self.root / "plain-raw"
        plain_root.mkdir()
        (plain_root / "topic.md").write_text("plain raw\n", encoding="utf-8")

        snapshot = wiki_common.git_snapshot(plain_root)

        self.assertFalse(snapshot["git_enabled"])
        self.assertFalse(snapshot["has_commits"])
        self.assertEqual(snapshot["short_head"], "no-git")
        self.assertEqual(snapshot["changed_files"], ["topic.md"])

    def test_compute_sync_status_handles_non_git_raw_directory(self) -> None:
        plain_root = self.root / "plain-sync"
        plain_root.mkdir()
        (plain_root / "topic.md").write_text("plain raw\n", encoding="utf-8")
        paths = wiki_common.ResolvedPaths(
            raw_dir=plain_root.resolve(),
            wiki_dir=self.wiki_dir.resolve(),
            config_path=None,
            source="test",
        )

        status = wiki_common.compute_sync_status(paths)

        self.assertTrue(status["needs_sync"])
        self.assertFalse(status["baseline_commit_recommended"])
        self.assertIn("not a git repository", " ".join(status["reasons"]).lower())
        self.assertIn("raw_git_init.py", " ".join(status["follow_up_actions"]))

    def test_compute_sync_status_detects_cleared_wiki_with_stale_metadata(self) -> None:
        paths = wiki_common.resolve_paths()
        snapshot = wiki_common.git_snapshot(paths.raw_dir)
        wiki_common.ensure_wiki_structure(paths.wiki_dir)
        wiki_common.write_sync_metadata(paths.wiki_dir, snapshot, "sync")
        wiki_common.write_source_map(paths.wiki_dir, {"source.md": "sources/source"})

        status = wiki_common.compute_sync_status(paths)

        self.assertTrue(status["needs_sync"])
        self.assertIn("source pages are missing", " ".join(status["reasons"]).lower())

    def test_raw_git_init_script_bootstraps_plain_directory(self) -> None:
        plain_root = self.root / "plain-init"
        plain_root.mkdir()
        (plain_root / "topic.md").write_text("plain raw\n", encoding="utf-8")
        os.environ["WIKI_RAW_DIR"] = str(plain_root)

        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "raw_git_init.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["created_repo"])
        self.assertFalse(payload["created_initial_commit"])
        self.assertTrue((plain_root / ".git").exists())
        self.assertFalse(payload["git"]["has_commits"])

    def test_raw_git_init_script_can_create_initial_commit(self) -> None:
        plain_root = self.root / "plain-init-commit"
        plain_root.mkdir()
        (plain_root / "topic.md").write_text("plain raw\n", encoding="utf-8")
        os.environ["WIKI_RAW_DIR"] = str(plain_root)

        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "raw_git_init.py"), "--initial-commit"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["created_repo"])
        self.assertTrue(payload["created_initial_commit"])
        self.assertTrue(payload["git"]["has_commits"])

    def test_wiki_quality_audit_flags_placeholder_pages(self) -> None:
        wiki_common.ensure_wiki_structure(self.wiki_dir)
        (self.wiki_dir / "concepts" / "draft.md").write_text(
            "---\n"
            "type: concept\n"
            "title: Draft\n"
            "---\n\n"
            "## Summary\n\n"
            "Auto-maintained concept page for Draft.\n",
            encoding="utf-8",
        )
        (self.wiki_dir / "index.md").write_text(
            "# Index\n\n## Concepts\n- [[concepts/draft]]: Auto-maintained concept page for Draft.\n",
            encoding="utf-8",
        )

        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_quality_audit.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("concepts/draft.md", payload["placeholder_pages"])
        self.assertFalse(payload["passes_editorial_gate"])
        self.assertTrue(payload["index_has_placeholders"])

    def test_wiki_git_init_script_bootstraps_plain_directory(self) -> None:
        git_dir = self.wiki_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_git_init.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["created_repo"])
        self.assertFalse(payload["created_initial_commit"])
        self.assertTrue((self.wiki_dir / ".git").exists())

    def test_wiki_git_init_script_can_create_initial_commit(self) -> None:
        git_dir = self.wiki_dir / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)
        (self.wiki_dir / "note.md").write_text("hello wiki\n", encoding="utf-8")

        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_git_init.py"), "--initial-commit"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["created_repo"])
        self.assertTrue(payload["created_initial_commit"])
        self.assertEqual(payload["git"]["dirty"], False)

    def test_wiki_commit_batch_script_commits_paths(self) -> None:
        git(self.wiki_dir, "init")
        git(self.wiki_dir, "config", "user.name", "Wiki User")
        git(self.wiki_dir, "config", "user.email", "wiki@example.com")
        (self.wiki_dir / "index.md").write_text("# Index\n\n", encoding="utf-8")
        git(self.wiki_dir, "add", "index.md")
        git(self.wiki_dir, "commit", "-m", "seed wiki")
        (self.wiki_dir / "concepts").mkdir(exist_ok=True)
        (self.wiki_dir / "concepts" / "draft.md").write_text("Draft\n", encoding="utf-8")

        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "wiki_commit_batch.py"),
                "--message",
                "Commit wiki batch",
                "--paths",
                "concepts/draft.md",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["committed"])
        self.assertEqual(git(self.wiki_dir, "log", "-1", "--pretty=%s"), "Commit wiki batch")

    def test_extract_title_and_summary_filters_boilerplate(self) -> None:
        raw_text = (
            "Skip To Main Content\n\n"
            "Account\n\n"
            "Settings\n\n"
            "# Solace Cloud Console\n\n"
            "The Solace Cloud Console is the single-pane-of-glass UI for managing services.\n\n"
            "Provide feedback\n"
        )

        title, summary = wiki_common.extract_title_and_summary(Path("cloud-console.md"), raw_text)

        self.assertEqual(title, "Solace Cloud Console")
        self.assertEqual(
            summary,
            "The Solace Cloud Console is the single-pane-of-glass UI for managing services.",
        )

    def test_extract_title_and_summary_skips_link_only_lines(self) -> None:
        raw_text = (
            "# Example Title\n\n"
            "| [](https://dev.solace.com) |\n\n"
            "## Administration Tasks\n\n"
            "This page explains the real content.\n"
        )

        title, summary = wiki_common.extract_title_and_summary(Path("example.md"), raw_text)

        self.assertEqual(title, "Example Title")
        self.assertEqual(summary, "This page explains the real content.")

    def test_bootstrap_wiki_script_creates_expected_structure(self) -> None:
        self.wiki_dir.rmdir()
        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "bootstrap_wiki.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue((self.wiki_dir / "sources").is_dir())
        self.assertTrue((self.wiki_dir / "entities").is_dir())
        self.assertTrue((self.wiki_dir / "concepts").is_dir())
        self.assertTrue((self.wiki_dir / "analyses").is_dir())
        self.assertTrue((self.wiki_dir / ".steven-wiki").is_dir())
        self.assertTrue((self.wiki_dir / "index.md").exists())
        self.assertTrue((self.wiki_dir / "log.md").exists())

    def test_generate_slash_commands_script_writes_outputs(self) -> None:
        output_dir = self.root / "generated"
        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "generate_slash_commands.py"),
                "--output-dir",
                str(output_dir),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["targets"]["codex"]), len(COMMANDS))
        self.assertEqual(len(manifest["targets"]["claude"]), len(COMMANDS))
        self.assertTrue((output_dir / "codex" / "wiki-sync.md").exists())
        self.assertTrue((output_dir / "claude" / "wiki-delete-page.md").exists())

    def test_wiki_ingest_creates_source_and_related_pages(self) -> None:
        raw_file = self.raw_dir / "topic.md"
        raw_file.write_text(
            "# Event Mesh\n\nSolace Event Mesh improves messaging architecture for Korea team.\n",
            encoding="utf-8",
        )
        git(self.raw_dir, "add", "topic.md")
        git(self.raw_dir, "commit", "-m", "add topic")
        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "wiki_ingest.py"),
                "topic.md",
                "--update-sync-marker",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        source_page = self.wiki_dir / "sources" / "topic.md"
        self.assertTrue(source_page.exists())
        source_text = source_page.read_text(encoding="utf-8")
        self.assertNotIn("raw_path:", source_text)
        self.assertNotIn("raw_commit:", source_text)
        source_map = json.loads((self.wiki_dir / ".steven-wiki" / "source_map.json").read_text(encoding="utf-8"))
        self.assertEqual(source_map["topic.md"], "sources/topic")
        self.assertTrue((self.wiki_dir / "index.md").exists())
        self.assertTrue((self.wiki_dir / "log.md").exists())
        related_pages = list((self.wiki_dir / "concepts").glob("*.md")) + list((self.wiki_dir / "entities").glob("*.md"))
        self.assertTrue(related_pages)

    def test_wiki_ingest_updates_existing_source_page(self) -> None:
        raw_file = self.raw_dir / "topic.md"
        raw_file.write_text("Initial content about Solace event mesh.\n", encoding="utf-8")
        git(self.raw_dir, "add", "topic.md")
        git(self.raw_dir, "commit", "-m", "add source")
        subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_ingest.py"), "topic.md"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        raw_file.write_text("Updated content about Solace event mesh and resilience.\n", encoding="utf-8")
        git(self.raw_dir, "add", "topic.md")
        git(self.raw_dir, "commit", "-m", "update source")
        subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_ingest.py"), "topic.md"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        source_page = self.wiki_dir / "sources" / "topic.md"
        metadata, body = wiki_common.read_wiki_page(source_page)
        self.assertEqual(metadata["type"], "source")
        self.assertIn("Updated content", body)

    def test_wiki_sync_bootstraps_from_unborn_raw_directory(self) -> None:
        raw_file = self.raw_dir / "docs" / "overview.md"
        raw_file.parent.mkdir(parents=True)
        raw_file.write_text("Overview of Solace broker operations.\n", encoding="utf-8")
        second_file = self.raw_dir / "docs" / "setup.md"
        second_file.write_text("Setup notes for event broker deployment.\n", encoding="utf-8")

        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "wiki_sync.py"),
                "--update-sync-marker",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["synced_raw_files"], 3)
        self.assertTrue((self.wiki_dir / "sources" / "docs-overview.md").exists())
        self.assertTrue((self.wiki_dir / "sources" / "docs-setup.md").exists())
        self.assertTrue((self.wiki_dir / ".steven-wiki" / "last_sync.json").exists())

    def test_wiki_sync_handles_update_delete_and_add(self) -> None:
        keep_file = self.raw_dir / "keep.md"
        remove_file = self.raw_dir / "remove.md"
        keep_file.write_text("Keep original content.\n", encoding="utf-8")
        remove_file.write_text("Remove this page later.\n", encoding="utf-8")
        git(self.raw_dir, "add", "keep.md", "remove.md")
        git(self.raw_dir, "commit", "-m", "seed raw")

        subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "wiki_sync.py"),
                "--update-sync-marker",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        keep_file.write_text("Keep updated content with resilience guidance.\n", encoding="utf-8")
        remove_file.unlink()
        new_file = self.raw_dir / "new.md"
        new_file.write_text("Brand new content for added source.\n", encoding="utf-8")
        git(self.raw_dir, "add", "-A")
        git(self.raw_dir, "commit", "-m", "mutate raw")

        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "wiki_sync.py"),
                "--update-sync-marker",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue((self.wiki_dir / "sources" / "keep.md").exists())
        self.assertFalse((self.wiki_dir / "sources" / "remove.md").exists())
        self.assertTrue((self.wiki_dir / "sources" / "new.md").exists())
        source_map = json.loads((self.wiki_dir / ".steven-wiki" / "source_map.json").read_text(encoding="utf-8"))
        self.assertIn("keep.md", source_map)
        self.assertIn("new.md", source_map)
        self.assertNotIn("remove.md", source_map)
        _metadata, body = wiki_common.read_wiki_page(self.wiki_dir / "sources" / "keep.md")
        self.assertIn("Keep updated content", body)
        self.assertIn("sources/remove.md", payload["deleted_wiki_pages"])

    def test_wiki_query_returns_citations_and_can_save_analysis(self) -> None:
        raw_file = self.raw_dir / "topic.md"
        raw_file.write_text("Event mesh supports distributed messaging for Solace systems.\n", encoding="utf-8")
        git(self.raw_dir, "add", "topic.md")
        git(self.raw_dir, "commit", "-m", "add source")
        subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_ingest.py"), "topic.md"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        completed = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "wiki_query.py"),
                "What does event mesh support?",
                "--save-to",
                "mesh-answer",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["citations"])
        self.assertTrue((self.wiki_dir / "analyses" / "mesh-answer.md").exists())

    def test_wiki_lint_reports_orphan_pages_and_sync_attention(self) -> None:
        wiki_common.ensure_wiki_structure(self.wiki_dir)
        orphan = self.wiki_dir / "concepts" / "orphan.md"
        wiki_common.write_wiki_page(
            orphan,
            {"type": "concept", "title": "Orphan", "last_reviewed": "2026-04-11"},
            "## Summary\n\nStandalone concept page.\n",
        )
        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_lint.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("concepts/orphan", payload["orphan_pages"])
        self.assertTrue(payload["sync_needs_attention"])

    def test_wiki_session_start_reports_prompt_needed_after_raw_change(self) -> None:
        wiki_common.ensure_wiki_structure(self.wiki_dir)
        snapshot = wiki_common.git_snapshot(self.raw_dir)
        wiki_common.write_sync_metadata(self.wiki_dir, snapshot, "ingest")
        (self.raw_dir / "new-note.md").write_text("new information\n", encoding="utf-8")
        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_session_start.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["needs_sync"])
        self.assertTrue(payload["should_prompt_user"])

    def test_wiki_session_start_reports_baseline_commit_follow_up_for_unborn_repo(self) -> None:
        fresh_root = self.root / "fresh-session"
        fresh_root.mkdir()
        git(fresh_root, "init")
        git(fresh_root, "config", "user.name", "Test User")
        git(fresh_root, "config", "user.email", "test@example.com")
        (fresh_root / "draft.md").write_text("draft\n", encoding="utf-8")
        env = os.environ.copy()
        env["WIKI_RAW_DIR"] = str(fresh_root)

        completed = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "wiki_session_start.py")],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["baseline_commit_recommended"])
        self.assertFalse(payload["raw_has_commits"])
        self.assertTrue(payload["follow_up_actions"])


if __name__ == "__main__":
    unittest.main()
