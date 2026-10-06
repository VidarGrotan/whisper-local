"""Guard against Whisper Local running inside a Store (MSIX) app's container.

Codex desktop redirects %APPDATA% for processes it launches, which split this
install into two divergent config folders until 2026-10-06.
"""

import ctypes
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@unittest.skipUnless(sys.platform == "win32", "MSIX containers are Windows-only")
class AppPackageDetectionTests(unittest.TestCase):
    def _fake_kernel32(self, package_name):
        """Mimic GetCurrentPackageFullName for a packaged or unpackaged process."""
        def get_name(length_ref, buffer):
            length = ctypes.cast(length_ref, ctypes.POINTER(ctypes.c_uint32)).contents
            if package_name is None:
                return 15700  # APPMODEL_ERROR_NO_PACKAGE
            if buffer is None:
                length.value = len(package_name) + 1
                return 122  # ERROR_INSUFFICIENT_BUFFER
            buffer.value = package_name
            return 0
        return mock.Mock(GetCurrentPackageFullName=get_name)

    def test_unpackaged_process_is_not_in_package(self):
        from whisper_key.platform.windows import app
        with mock.patch.object(app.ctypes, "windll",
                               mock.Mock(kernel32=self._fake_kernel32(None))):
            self.assertIsNone(app.current_app_package_name())
            self.assertFalse(app.is_running_in_app_package())

    def test_packaged_process_reports_package_name(self):
        """A Codex-launched process must be recognised, or settings split again."""
        from whisper_key.platform.windows import app
        name = "OpenAI.Codex_1.0.0.0_x64__2p2nqsd0c76g0"
        with mock.patch.object(app.ctypes, "windll",
                               mock.Mock(kernel32=self._fake_kernel32(name))):
            self.assertEqual(app.current_app_package_name(), name)
            self.assertTrue(app.is_running_in_app_package())

    def test_this_test_process_is_unpackaged(self):
        """The real API call works; test runners are never packaged here."""
        from whisper_key.platform.windows import app
        self.assertFalse(app.is_running_in_app_package())


@unittest.skipUnless(sys.platform == "win32", "MSIX containers are Windows-only")
class RelaunchOutsidePackageTests(unittest.TestCase):
    def test_packaged_start_hands_off_to_checkout_launcher(self):
        from whisper_key import main
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            (checkout / "whisper-local-autostart.vbs").write_text("", encoding="utf-8")
            fake_main_file = checkout / "src" / "whisper_key" / "main.py"
            with mock.patch.object(main.app, "current_app_package_name",
                                   return_value="OpenAI.Codex_x"), \
                    mock.patch.object(main.app, "relaunch_outside_app_package") as relaunch, \
                    mock.patch.object(main, "__file__", str(fake_main_file)):
                self.assertTrue(main._relaunch_if_inside_app_package())
            relaunch.assert_called_once_with(checkout / "whisper-local-autostart.vbs")

    def test_unpackaged_start_continues(self):
        from whisper_key import main
        with mock.patch.object(main.app, "current_app_package_name", return_value=None), \
                mock.patch.object(main.app, "relaunch_outside_app_package") as relaunch:
            self.assertFalse(main._relaunch_if_inside_app_package())
        relaunch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
