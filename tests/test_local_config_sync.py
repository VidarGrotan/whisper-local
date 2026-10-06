"""Exercise tools/sync_local_config.py against throwaway config folders.

The tool is the guard that keeps this PC's live config equal to local-config/,
so a silent pass on drift would let the 2026-10-06 regressions return.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sync_local_config as sync  # noqa: E402


class LocalConfigSyncTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.live = self.root / "whisperkey"
        self.local_appdata = self.root / "local"
        self.local_appdata.mkdir()

    def tearDown(self):
        self._temp.cleanup()

    def _check(self):
        return [p for p in sync.check(self.live, self.local_appdata)
                if sync.API_KEY_ENV not in p]

    def test_install_into_empty_folder_then_check_is_clean(self):
        sync.install(self.live, "t1")
        self.assertEqual(self._check(), [])

    def test_check_reports_bare_settings_as_drift(self):
        """The 2026-10-06 state: base model, no NTNU routes, no HyperX."""
        self.live.mkdir()
        (self.live / "user_settings.yaml").write_text(
            "whisper:\n  model: base\n", encoding="utf-8")
        problems = "\n".join(self._check())
        self.assertIn("whisper.model: expected", problems)
        self.assertIn("postprocess: missing", problems)
        self.assertIn("audio: missing", problems)

    def test_install_keeps_live_extras_and_backs_up(self):
        self.live.mkdir()
        (self.live / "user_settings.yaml").write_text(
            "audio:\n  input_device: 7\nwhisper:\n  model: base\n", encoding="utf-8")
        sync.install(self.live, "t2")

        settings = sync.load_yaml(self.live / "user_settings.yaml")
        self.assertEqual(settings["audio"]["input_device"], 7)
        self.assertEqual(settings["whisper"]["model"], "large-v3-turbo")
        self.assertTrue((self.live / "backups" / "user_settings.yaml.t2").is_file())
        self.assertEqual(self._check(), [])

    def test_install_preserves_long_prompts_exactly(self):
        sync.install(self.live, "t3")
        canonical = sync.load_yaml(sync.CANONICAL_DIR / "user_settings.yaml")
        live = sync.load_yaml(self.live / "user_settings.yaml")
        routes = "postprocess", "openai_compatible", "routes"
        canonical_en = canonical[routes[0]][routes[1]][routes[2]]["en"]["prompt"]
        live_en = live[routes[0]][routes[1]][routes[2]]["en"]["prompt"]
        self.assertEqual(str(live_en), str(canonical_en))

    def test_check_flags_app_package_config_folder(self):
        sync.install(self.live, "t4")
        stray = self.local_appdata / "Packages" / "OpenAI.Codex_x" / "LocalCache" / "Roaming" / "whisperkey"
        stray.mkdir(parents=True)
        self.assertTrue(any("app package" in p for p in self._check()))

    def test_migration_merges_history_and_retires_folder(self):
        self.live.mkdir()
        package = self.root / "pkg" / "whisperkey"
        package.mkdir(parents=True)
        shared = json.dumps({"timestamp": "2026-09-01T10:00:00", "text": "same"})
        (self.live / "transcripts.jsonl").write_text(
            shared + "\n" + json.dumps({"timestamp": "2026-10-06T20:00:00", "text": "real"}) + "\n",
            encoding="utf-8")
        (package / "transcripts.jsonl").write_text(
            json.dumps({"timestamp": "2026-08-26T09:00:00", "text": "codex"}) + "\n" + shared + "\n",
            encoding="utf-8")
        (package / "user_settings.yaml.pre-ntnu").write_text("x: 1\n", encoding="utf-8")

        retired = sync.migrate_package_folder(package, self.live, "t5")

        lines = (self.live / "transcripts.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(l)["text"] for l in lines], ["codex", "same", "real"])
        self.assertFalse(package.exists())
        self.assertTrue(retired.is_dir())
        self.assertTrue((self.live / "backups" / "package-user_settings.yaml.pre-ntnu.t5").is_file())


if __name__ == "__main__":
    unittest.main()
