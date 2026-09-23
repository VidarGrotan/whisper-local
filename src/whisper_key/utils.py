# utils.py
# Small cross-cutting helpers shared by nearly every module: locating the user's
# config directory, resolving bundled asset paths (source checkout vs installed
# wheel vs frozen .exe), hotkey string parsing/prettifying, version lookup, and
# the OptionalComponent shim used for gracefully-absent dependencies.
import os
import subprocess
import sys
import importlib.resources
import tomllib
from pathlib import Path

class OptionalComponent:
    def __init__(self, component):
        self._component = component
    
    def __getattr__(self, name):
        if self._component and hasattr(self._component, name):
            attr = getattr(self._component, name)
            return attr
        else:
            # Return a no-op function for missing methods/attributes
            return lambda *args, **kwargs: None


def beautify_hotkey(hotkey_string: str) -> str:
    if not hotkey_string:
        return ""

    return hotkey_string.upper()

def parse_hotkey(hotkey_string: str) -> list:
    if not hotkey_string:
        return []
    return hotkey_string.lower().split('+')

def is_installed_package():
    # Check if running from an installed package
    return 'site-packages' in __file__

def get_user_app_data_path():
    # On Linux CI / unsupported platforms, .platform doesn't ship a `paths`
    # module. Fall back to ~/.whisperkey so tests and tools that just need a
    # directory keep working — actual app functionality is Windows/macOS only.
    try:
        from .platform import paths
        whisperkey_dir = paths.get_app_data_path()
    except ImportError:
        whisperkey_dir = Path.home() / ".whisperkey"
    whisperkey_dir.mkdir(parents=True, exist_ok=True)
    return str(whisperkey_dir)

def open_file(path):
    # Best-effort on Linux: log only, don't crash. Real Windows/macOS path goes
    # through the platform module's xdg-open / explorer.exe wrapper.
    try:
        from .platform import paths
        paths.open_file(path)
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(f"open_file('{path}'): unsupported platform")

def resolve_asset_path(relative_path: str) -> str:
    if not relative_path or os.path.isabs(relative_path):
        return relative_path

    if is_installed_package():
        files = importlib.resources.files("whisper_key")
        return str(files / relative_path)

    return str(Path(__file__).parent / relative_path)

def setup_portaudio_path():
    # Called first in main.py - platform module imports break WASAPI
    if sys.platform != 'win32':
        return
    assets_dir = Path(resolve_asset_path('platform/windows/assets'))
    if assets_dir.exists():
        os.environ['PATH'] = str(assets_dir) + os.pathsep + os.environ.get('PATH', '')

# Find pythonw.exe for the interpreter we're running under. It normally sits
# beside python.exe, but not always: a venv created with --without-pip, and some
# Microsoft Store layouts, ship python.exe alone. Fall back to the BASE
# interpreter's pythonw (sys._base_executable) before giving up.
def _windowless_python(exe: str) -> str:
    candidates = [Path(exe).with_name("pythonw.exe")]
    base = getattr(sys, "_base_executable", None)
    if base and base != exe:
        candidates.append(Path(base).with_name("pythonw.exe"))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return exe


# The single answer to "what command relaunches this app?". Used by autostart
# (windowless=True, so login doesn't pop a console) and by the tray's Restart
# item (windowless=False, so a user who launched from a console keeps it).
#
# Never build this from sys.argv. For a pip install, argv[0] is the console-script
# path, and pip only ships a compiled `whisper-local.exe` stub there — no plain
# script file — so handing it to python.exe fails with "can't open file"
# (issue #3). Invoking the module with -m is layout-independent.
#
# sys.executable is equally wrong under the standalone build: pyapp unpacks a
# private CPython and runs the app with it, so sys.executable is that interpreter,
# not the .exe. pyapp exports the real path as $PYAPP (PYAPP_PASS_LOCATION=1),
# which is what issue #2 turned on.
def build_relaunch_command(windowless: bool = False) -> list:
    exe = sys.executable

    pyapp_exe = os.environ.get("PYAPP", "")
    if pyapp_exe and os.path.isfile(pyapp_exe):
        return [pyapp_exe]

    # Frozen builds (PyInstaller-style) genuinely do have sys.executable == the app.
    if getattr(sys, "frozen", False) or exe.lower().endswith("whisper-local.exe"):
        return [exe]

    # This PC's editable checkout needs the project launcher to prepend the
    # NVIDIA runtime DLL directories.  A plain pythonw -m launch can appear to
    # start at login while missing the installed CUDA-aware operating context.
    # Keep this deliberately narrow: only the interpreter inside this checkout's
    # own .venv receives the override; normal pip and packaged installs retain
    # the portable command below.
    if windowless and sys.platform == "win32":
        repo_root = Path(__file__).resolve().parents[2]
        local_scripts = repo_root / ".venv" / "Scripts"
        try:
            is_local_venv = Path(exe).resolve().parent == local_scripts.resolve()
        except OSError:
            is_local_venv = False
        launcher = repo_root / "whisper-local-autostart.vbs"
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        wscript = Path(system_root) / "System32" / "wscript.exe"
        if is_local_venv and launcher.is_file():
            return [str(wscript), str(launcher)]

    runner = _windowless_python(exe) if (windowless and sys.platform == "win32") else exe
    return [runner, "-m", "whisper_key.main"]


def restart_or_exit(message_restart, message_exit):
    pyapp_exe = os.environ.get('PYAPP', '')
    if os.path.isfile(pyapp_exe):
        print(message_restart)
        subprocess.Popen([pyapp_exe], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        print(message_exit)
    sys.exit(0)


def get_version():
    if is_installed_package():
        import importlib.metadata
        return importlib.metadata.version("whisper-local")

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, 'rb') as f:
        data = tomllib.load(f)
        return f"{data['project']['version']}-dev"
