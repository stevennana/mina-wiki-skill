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


if __name__ == "__main__":
    unittest.main()
