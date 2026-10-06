# platform/windows/app.py
# Windows app-lifecycle bits: single-keypress input (msvcrt), the thread
# requirements the main loop must respect, and detection of a launch from
# inside a Store (MSIX) app's container, whose redirected %APPDATA% would
# give Whisper Local a private, divergent copy of its settings.
# macOS mirror: platform/macos/app.py (NSApplication run loop, which DOES
# require the main thread).
import ctypes
import msvcrt
import subprocess

# ============================================================================
# Main loop
# ============================================================================

def setup():
    pass

def run_event_loop(shutdown_event):
    while not shutdown_event.wait(timeout=0.1):
        pass

def getch():
    return msvcrt.getwch()

# ============================================================================
# App-package (MSIX) container detection
# ============================================================================
# Codex desktop is an MSIX app. Every process it launches inherits its package
# identity, and Windows redirects that process's %APPDATA% writes into
# %LOCALAPPDATA%\Packages\<package>\LocalCache\Roaming. Whisper Local started
# there silently runs on different settings, logs and history than the copy
# started from the Start menu or at login.

_ERROR_SUCCESS = 0
_ERROR_INSUFFICIENT_BUFFER = 122


# Return the package full name of this process, or None when unpackaged.
def current_app_package_name():
    try:
        get_name = ctypes.windll.kernel32.GetCurrentPackageFullName
    except AttributeError:
        return None  # Windows 7: app packages don't exist
    length = ctypes.c_uint32(0)
    result = get_name(ctypes.byref(length), None)
    if result != _ERROR_INSUFFICIENT_BUFFER:
        # APPMODEL_ERROR_NO_PACKAGE (15700) is the normal unpackaged answer.
        return None
    buffer = ctypes.create_unicode_buffer(length.value)
    if get_name(ctypes.byref(length), buffer) != _ERROR_SUCCESS:
        return None
    return buffer.value or None


def is_running_in_app_package():
    return current_app_package_name() is not None


# Hand the launch to the user's shell: explorer.exe forwards the request to the
# already-running desktop Explorer, so the new process starts outside the
# package container and sees the real %APPDATA%.
def relaunch_outside_app_package(launcher_path):
    subprocess.Popen(['explorer.exe', str(launcher_path)])
