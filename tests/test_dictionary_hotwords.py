"""Hotwords added from the tray, history window or CLI must stick and apply live.

Before 2026-10-06 a word added via "Add word to dictionary" only took effect
after a restart, was wiped by the running app's next settings save, and was
reverted by tools/sync_local_config.py because local-config/ never saw it.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ruamel.yaml import YAML  # noqa: E402

DEFAULTS = ROOT / "src" / "whisper_key" / "config.defaults.yaml"

CANONICAL = (
    "whisper:\n"
    "  model: large-v3-turbo\n"
    "  hotwords:\n"
    "    - Claude\n"
    "postprocess:\n"
    "  openai_compatible:\n"
    "    routes:\n"
    "      en:\n"
    "        prompt: |-\n"
    "          Line one.\n"
    "          Line two.\n"
)


def _hotwords(path):
    data = YAML().load(Path(path).read_text(encoding="utf-8"))
    return list(data["whisper"]["hotwords"])


class _TempUserDir(unittest.TestCase):
    """A throwaway %APPDATA%\\whisperkey plus a throwaway local-config file."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.user_dir = Path(self._temp.name) / "whisperkey"
        self.user_dir.mkdir()
        self.settings = self.user_dir / "user_settings.yaml"
        self.settings.write_text("whisper:\n  hotwords:\n    - Claude\n", encoding="utf-8")
        self.canonical = Path(self._temp.name) / "local-config-user_settings.yaml"
        self.canonical.write_text(CANONICAL, encoding="utf-8")
        for target in ("whisper_key.dictionary.get_user_app_data_path",
                       "whisper_key.config_manager.get_user_app_data_path"):
            patcher = mock.patch(target, return_value=str(self.user_dir))
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch("whisper_key.dictionary.LOCAL_CONFIG_SETTINGS", self.canonical)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _touch_later(self):
        """Ensure the next write gets a newer mtime than the loaded one."""
        later = time.time() + 5
        os.utime(self.settings, (later, later))


class DictionaryWriteTests(_TempUserDir):
    def test_add_word_updates_live_and_local_config(self):
        from whisper_key.dictionary import add_word
        self.assertTrue(add_word("NTNU"))
        self.assertEqual(_hotwords(self.settings), ["Claude", "NTNU"])
        self.assertEqual(_hotwords(self.canonical), ["Claude", "NTNU"])

    def test_add_word_keeps_local_config_prompts_intact(self):
        from whisper_key.dictionary import add_word
        add_word("NTNU")
        text = self.canonical.read_text(encoding="utf-8")
        self.assertIn("prompt: |-\n          Line one.\n          Line two.", text)
        self.assertIn("model: large-v3-turbo", text)

    def test_remove_word_updates_live_and_local_config(self):
        from whisper_key.dictionary import remove_word
        self.assertTrue(remove_word("Claude"))
        self.assertEqual(_hotwords(self.settings), [])
        self.assertEqual(_hotwords(self.canonical), [])

    def test_missing_local_config_is_skipped(self):
        from whisper_key.dictionary import add_word
        with mock.patch("whisper_key.dictionary.LOCAL_CONFIG_SETTINGS",
                        Path(self._temp.name) / "absent.yaml"):
            self.assertTrue(add_word("NTNU"))
        self.assertEqual(_hotwords(self.settings), ["Claude", "NTNU"])


class RunningAppHotwordTests(_TempUserDir):
    def test_settings_save_keeps_word_added_on_disk(self):
        """Tray save after a dialog add must not resurrect the startup list."""
        from whisper_key.config_manager import ConfigManager
        from whisper_key.dictionary import add_word

        config = ConfigManager(config_path=str(DEFAULTS), quiet=True)
        add_word("NTNU")
        self._touch_later()
        config.update_user_setting("audio", "preferred_input_device", "HyperX Quadcast")

        self.assertEqual(_hotwords(self.settings), ["Claude", "NTNU"])

    def test_get_hotwords_reflects_disk_changes(self):
        from whisper_key.config_manager import ConfigManager
        from whisper_key.dictionary import add_word

        config = ConfigManager(config_path=str(DEFAULTS), quiet=True)
        self.assertEqual(config.get_hotwords(), ["Claude"])
        add_word("NTNU")
        self._touch_later()
        self.assertEqual(config.get_hotwords(), ["Claude", "NTNU"])

    def test_recording_context_pushes_hotwords_to_engine(self):
        from whisper_key.state_manager import StateManager

        manager = StateManager.__new__(StateManager)
        manager.logger = mock.Mock()
        manager.config_manager = SimpleNamespace(
            get_whisper_config=lambda: {},
            get_hotwords=lambda: ["Claude", "NTNU"],
        )
        manager.app_rules = SimpleNamespace(match_for_foreground=lambda: None)
        manager.whisper_engine = mock.Mock()

        manager._apply_recording_context()

        manager.whisper_engine.set_hotwords.assert_called_once_with(["Claude", "NTNU"])


class AddWordDialogLaunchTests(unittest.TestCase):
    def test_tray_opens_dialog_in_its_own_process(self):
        """In-process, the dialog's Add button died beside the overlay's Tk thread."""
        from whisper_key.system_tray import SystemTray

        tray = SystemTray.__new__(SystemTray)
        tray.logger = mock.Mock()
        with mock.patch("subprocess.Popen") as popen:
            tray._open_add_word_dialog()

        command = popen.call_args.args[0]
        self.assertEqual(command[1:], ["-m", "whisper_key.main", "--add-word-dialog"])
        tray.logger.error.assert_not_called()


class EngineHotwordTests(unittest.TestCase):
    def test_engine_set_hotwords_formats_for_faster_whisper(self):
        from whisper_key.whisper_engine import WhisperEngine
        engine = WhisperEngine.__new__(WhisperEngine)
        engine.set_hotwords(["Claude", "NTNU"])
        self.assertEqual(engine.hotwords, "Claude, NTNU")
        engine.set_hotwords([])
        self.assertIsNone(engine.hotwords)


if __name__ == "__main__":
    unittest.main()
