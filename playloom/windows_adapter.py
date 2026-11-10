"""EXPERIMENTAL Windows helpers, not wired to the demo or enabled by default.

Requires Windows, `pip install mss pydirectinput-rgx`. The controller only
accepts a foreground window whose title contains an explicitly supplied string.
Use only with a game whose input and save files you control.
"""
from __future__ import annotations
import sys
import time
from .core import Action


def _require_windows() -> None:
    if sys.platform != "win32":
        raise OSError("Windows adapter only works on Windows")


def foreground_window(expected_title: str) -> tuple[int, tuple[int, int, int, int]]:
    """Check target before every operation; fail closed when focus is lost."""
    _require_windows()
    if len(expected_title.strip()) < 4:
        raise ValueError("Explicit target title must have at least 4 characters")
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("No foreground window")
    buf = ctypes.create_unicode_buffer(1024)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    if expected_title.casefold() not in buf.value.casefold():
        raise RuntimeError(f"Unexpected foreground window: {buf.value!r}")
    rect = (ctypes.c_long * 4)()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("Unable to inspect target window")
    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        raise RuntimeError("Invalid window bounds")
    return hwnd, (left, top, right, bottom)


class WindowsCapture:
    def __init__(self, expected_title: str):
        self.title = expected_title

    def screenshot(self) -> bytes:
        _, (l, t, r, b) = foreground_window(self.title)
        import mss
        from mss import tools
        with mss.mss() as sct:
            shot = sct.grab({"left": l, "top": t, "width": r - l, "height": b - t})
            return tools.to_png(shot.rgb, shot.size)  # PNG bytes


class WindowsInput:
    def __init__(self, expected_title: str):
        self.title = expected_title
        self.down: set[str] = set()

    def execute(self, action: Action) -> None:
        foreground_window(self.title)
        import pydirectinput
        try:
            self.down.add(action.key)
            pydirectinput.keyDown(action.key)
            time.sleep(action.duration)
        finally:
            pydirectinput.keyUp(action.key)
            self.down.discard(action.key)

    def release_all(self) -> None:
        import pydirectinput
        for k in list(self.down):
            try:
                pydirectinput.keyUp(k)
            finally:
                self.down.discard(k)