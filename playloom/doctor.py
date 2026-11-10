"""Windows read-only diagnostics for Playloom. Never sends keyboard input or HTTP."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from threading import Event

DEFAULT_TITLE = "Playloom Disposable Test Window"


def diagnose(*, target_title: str = DEFAULT_TITLE, output=print,
             require_windows_fn=None, target_cls=None, stop_cls=None,
             available=None) -> int:
    """Check optional dependencies, target identity, and global F12 availability.

    A successful doctor run is not a substitute for an actual keyboard test.
    All probes are read-only except registering/unregistering F12 temporarily.
    """
    from .windows_adapter import EmergencyStop, TargetWindow, require_windows
    require_windows_fn = require_windows_fn or require_windows
    target_cls = target_cls or TargetWindow
    stop_cls = stop_cls or EmergencyStop
    available = available or importlib.util.find_spec

    output(f"Platform: {sys.platform}; Python: {sys.version_info.major}.{sys.version_info.minor}")
    missing = []
    for module in ("mss", "pydirectinput", "tkinter"):
        if available(module) is None:
            output(f"[MISSING] {module}")
            missing.append(module)
        else:
            output(f"[OK] {module}")
    if missing:
        output("Install optional packages with: python -m pip install mss pydirectinput-rgx")
        if "tkinter" in missing:
            output("Tkinter normally ships with Windows Python; repair your Python installation if missing.")
        return 2

    try:
        require_windows_fn()
    except OSError as exc:
        output(f"[UNSUPPORTED] {exc}")
        return 2

    try:
        target = target_cls(target_title)
        output(f"[OK] One visible window matches exact title: {target.title!r}")
    except (RuntimeError, ValueError, OSError) as exc:
        output(f"[BLOCKED] Target window not ready: {exc}")
        output("Start another terminal: python -m playloom.disposable_window")
        return 2

    try:
        target.check()
        output("[OK] Target is currently foreground")
    except RuntimeError:
        output("[INFO] Target is not foreground. This is normal while the doctor terminal is active.")

    stopper = stop_cls(Event(), lambda: None)
    try:
        stopper.start()
        output("[OK] F12 global emergency hotkey was available for registration")
    except RuntimeError:
        output("[BLOCKED] F12 global emergency hotkey unavailable; live control must stay disabled")
        return 2
    finally:
        stopper.close()

    output("Diagnostics passed. No key was pressed, no screenshot was uploaded.")
    output("Next: verify one actual Right press and F12 on this disposable window.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-title", default=DEFAULT_TITLE)
    args = parser.parse_args(argv)
    return diagnose(target_title=args.target_title)


if __name__ == "__main__":
    raise SystemExit(main())
