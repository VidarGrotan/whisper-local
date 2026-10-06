# platform/macos/app.py
# macOS app lifecycle: runs an NSApplication as an accessory (no Dock icon) and
# pumps its run loop, which Cocoa requires on the MAIN thread — the reason the
# platform layer exposes thread requirements at all.
# Windows mirror: platform/windows/app.py (no such constraint).
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSEventMaskAny, NSDefaultRunLoopMode
from Foundation import NSDate, NSObject

class AppDelegate(NSObject):
    def applicationSupportsSecureRestorableState_(self, app):
        return True

_delegate = None

def setup():
    global _delegate
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    _delegate = AppDelegate.alloc().init()
    app.setDelegate_(_delegate)

def getch():
    import tty
    import termios
    import sys
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# Windows-only concern (MSIX %APPDATA% redirection); macOS has no equivalent.
def current_app_package_name():
    return None

def is_running_in_app_package():
    return False

def relaunch_outside_app_package(launcher_path):
    pass

def run_event_loop(shutdown_event):
    app = NSApplication.sharedApplication()
    while not shutdown_event.is_set():
        event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
            NSEventMaskAny,
            NSDate.dateWithTimeIntervalSinceNow_(0.1),
            NSDefaultRunLoopMode,
            True
        )
        if event:
            app.sendEvent_(event)
