"""Exercise the Windows launcher executable through its diagnostic interface.

The test protects the CUDA-aware paths required by the installed local build.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "WhisperLocalLauncher.exe"


@unittest.skipUnless(sys.platform == "win32", "Windows launcher is Windows-only")
class WindowsLauncherTests(unittest.TestCase):
    def _diagnostics(self, *forwarded_args):
        self.assertTrue(
            LAUNCHER.is_file(),
            "WhisperLocalLauncher.exe must be built from the repository source",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "launcher-diagnostics.txt"
            subprocess.run(
                [
                    str(LAUNCHER),
                    "--launcher-diagnostics",
                    str(output),
                    *forwarded_args,
                ],
                cwd=ROOT,
                check=True,
                timeout=10,
            )
            self.assertTrue(output.is_file(), "launcher did not write diagnostics")
            return dict(
                line.split("=", 1)
                for line in output.read_text(encoding="utf-8").splitlines()
            )

    def test_launcher_uses_repo_executable_and_cuda_runtime(self):
        """A launcher that drops a CUDA path or targets another install must fail."""
        diagnostics = self._diagnostics()
        site_packages = ROOT / ".venv" / "Lib" / "site-packages"
        expected_prefix = os.pathsep.join(
            str(site_packages / relative)
            for relative in (
                Path("nvidia/cuda_runtime/bin"),
                Path("nvidia/cublas/bin"),
                Path("nvidia/cudnn/bin"),
            )
        )

        self.assertEqual(diagnostics["PROJECT"], str(ROOT))
        self.assertEqual(
            diagnostics["TARGET"],
            str(ROOT / ".venv" / "Scripts" / "whisper-local.exe"),
        )
        self.assertEqual(diagnostics["WORKING_DIRECTORY"], str(ROOT))
        self.assertEqual(diagnostics["PATH_PREFIX"], expected_prefix)

    def test_launcher_preserves_forwarded_arguments(self):
        """Dropping command-line options would break manual diagnostic starts."""
        diagnostics = self._diagnostics("--doctor", "value with spaces")
        self.assertEqual(diagnostics["ARGUMENT_0"], "--doctor")
        self.assertEqual(diagnostics["ARGUMENT_1"], "value with spaces")


if __name__ == "__main__":
    unittest.main()
