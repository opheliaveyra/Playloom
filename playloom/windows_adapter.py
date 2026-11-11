"""Opt-in Windows window capture and bounded keyboard control."""
from __future__ import annotations
import ctypes
import sys
import threading
import time
from ctypes import wintypes
from .core import Action, ClickAction, KeyClickAction

def require_windows():
    if sys.platform != "win32":
        raise OSError("Live capture is available only on Windows")

class TargetWindow:
    def __init__(self, title, user32=None):
        require_windows()
        if len(title.strip()) < 4:
            raise ValueError("Target title must contain at least four characters")
        self.title = title.strip()
        self.user32 = user32 or ctypes.windll.user32
        matches = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def collect(hwnd, _):
            if self.user32.IsWindowVisible(hwnd) and self._title(hwnd) == self.title:
                matches.append(hwnd)
            return True
        if not self.user32.EnumWindows(callback_type(collect), 0):
            raise RuntimeError("Unable to enumerate windows")
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one visible window titled {self.title!r}; found {len(matches)}")
        self.hwnd = matches[0]

    def _title(self, hwnd):
        buf = ctypes.create_unicode_buffer(self.user32.GetWindowTextLengthW(hwnd) + 1)
        self.user32.GetWindowTextW(hwnd, buf, len(buf))
        return buf.value

    def check(self):
        if self.user32.GetForegroundWindow() != self.hwnd or not self.user32.IsWindowVisible(self.hwnd) or self._title(self.hwnd) != self.title:
            raise RuntimeError("Target window lost focus, visibility, or title")
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(self.hwnd, ctypes.byref(rect)) or rect.right <= rect.left or rect.bottom <= rect.top:
            raise RuntimeError("Invalid target window bounds")
        return rect.left, rect.top, rect.right, rect.bottom

    def client_rect(self):
        """Return only the window content area, excluding title bar and borders."""
        rect = wintypes.RECT()
        if not self.user32.GetClientRect(self.hwnd, ctypes.byref(rect)):
            raise RuntimeError("Cannot locate target client area")
        origin = wintypes.POINT(rect.left, rect.top)
        corner = wintypes.POINT(rect.right, rect.bottom)
        if not self.user32.ClientToScreen(self.hwnd, ctypes.byref(origin)):
            raise RuntimeError("Cannot map target client area")
        if not self.user32.ClientToScreen(self.hwnd, ctypes.byref(corner)):
            raise RuntimeError("Cannot map target client area")
        if corner.x <= origin.x or corner.y <= origin.y:
            raise RuntimeError("Empty target client area")
        return origin.x, origin.y, corner.x, corner.y

def clipped_rect(rect, monitors):
    """Intersect window bounds with virtual desktop bounds, including negative origins."""
    left, top, right, bottom = rect
    desktop = monitors[0]
    x, y = max(left, desktop["left"]), max(top, desktop["top"])
    r = min(right, desktop["left"] + desktop["width"])
    b = min(bottom, desktop["top"] + desktop["height"])
    if r <= x or b <= y:
        raise RuntimeError("Target window is outside the visible desktop")
    return {"left": x, "top": y, "width": r - x, "height": b - y}

class WindowsCapture:
    def __init__(self, target):
        self.target = target
        self.last_frame_rect = None
        self.last_window_rect = None
        self.last_client_rect = None

    def screenshot(self):
        rect = self.target.check()
        import mss
        from mss import tools
        with mss.mss() as sct:
            bounds = clipped_rect(rect, sct.monitors)
            shot = sct.grab(bounds)
            if self.target.check() != rect:
                raise RuntimeError("Target moved during screenshot")
            png = tools.to_png(shot.rgb, shot.size)
            client_rect = self.target.client_rect()
            if self.target.check() != rect:
                raise RuntimeError("Target moved during client-area check")
            self.last_frame_rect = bounds
            self.last_window_rect = rect
            self.last_client_rect = client_rect
            return png

class WindowsInput:
    def __init__(self, target, stop_event, driver=None, *, frame_source=None, allow_mouse=False):
        self.target, self.stop_event = target, stop_event
        if driver is None:
            import pydirectinput as driver
        self.driver = driver
        self.frame_source = frame_source
        self.allow_mouse = allow_mouse
        self.mouse_down = False
        self.down = set()
        self.lock = threading.RLock()
    def execute(self, action: Action | ClickAction | KeyClickAction):
        if not isinstance(action, (Action, ClickAction, KeyClickAction)):
            raise TypeError("Validated Action required")
        self.target.check()
        if self.stop_event.is_set():
            return
        if isinstance(action, (ClickAction, KeyClickAction)):
            if not self.allow_mouse:
                raise RuntimeError("Mouse control requires explicit opt-in")
            self._click(action, held_key=action.key if isinstance(action, KeyClickAction) else None)
            return
        with self.lock:
            self.target.check()
            if self.stop_event.is_set():
                return
            self.down.add(action.key)
            try:
                self.driver.keyDown(action.key)
            except BaseException:
                self.release_all()
                raise
        try:
            deadline = time.monotonic() + action.duration
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self.stop_event.wait(min(0.01, remaining)):
                    raise RuntimeError("Emergency stop")
                self.target.check()
            self.target.check()
        finally:
            self.release_all()
    def _click(self, action: ClickAction | KeyClickAction, *, held_key: str | None = None):
        frame = self.frame_source
        if frame is None or frame.last_frame_rect is None or frame.last_window_rect is None:
            raise RuntimeError("A fresh captured frame is required for mouse input")
        window_rect = frame.last_window_rect
        bounds = frame.last_frame_rect
        client = getattr(frame, "last_client_rect", None)
        if client is None:
            raise RuntimeError("Observed client area is required for mouse input")
        if self.target.check() != window_rect:
            raise RuntimeError("Target window moved after observation")
        x = bounds["left"] + round(action.x * (bounds["width"] - 1))
        y = bounds["top"] + round(action.y * (bounds["height"] - 1))
        if not (bounds["left"] <= x < bounds["left"] + bounds["width"] and
                bounds["top"] <= y < bounds["top"] + bounds["height"]):
            raise RuntimeError("Mouse point is outside the observed frame")
        if not (client[0] <= x < client[2] and client[1] <= y < client[3]):
            raise RuntimeError("Mouse point is outside the game's client area")
        with self.lock:
            if self.stop_event.is_set():
                return
            if self.target.check() != window_rect:
                raise RuntimeError("Target changed before mouse movement")
            if held_key is not None:
                self.down.add(held_key)
                try:
                    self.driver.keyDown(held_key)
                except BaseException:
                    self.release_all()
                    raise
            try:
                self.driver.moveTo(x, y)
            except BaseException:
                self.release_all()
                raise
            if self.stop_event.is_set() or self.target.check() != window_rect:
                self.release_all()
                raise RuntimeError("Target changed before mouse press")
            self.mouse_down = True
            try:
                self.driver.mouseDown(button="left")
            except BaseException:
                self.release_all()
                raise
        try:
            deadline = time.monotonic() + action.duration
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if self.stop_event.wait(min(0.01, remaining)):
                    raise RuntimeError("Emergency stop")
                if self.target.check() != window_rect:
                    raise RuntimeError("Target moved during mouse click")
            if self.target.check() != window_rect:
                raise RuntimeError("Target moved during mouse click")
        finally:
            self.release_all()

    def release_all(self):
        with self.lock:
            keys = list(self.down)
            self.down.clear()
            try:
                if self.mouse_down:
                    self.mouse_down = False
                    self.driver.mouseUp(button="left")
            finally:
                for key in keys:
                    self.driver.keyUp(key)

class EmergencyStop:
    """Register a system-wide F12 hotkey; live input requires ready=True."""
    def __init__(self, stop_event, release, user32=None):
        require_windows()
        self.stop_event, self.release = stop_event, release
        self.user32 = user32 or ctypes.windll.user32
        self.ready = threading.Event()
        self.error = None
        self.thread = None
        self.thread_id = None
    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self.ready.wait(3) or self.error:
            raise RuntimeError("F12 emergency hotkey registration failed") from self.error
    def _run(self):
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        if not self.user32.RegisterHotKey(None, 1, 0x4000, 0x7B):
            self.error = RuntimeError("F12 is unavailable")
            self.ready.set()
            return
        self.ready.set()
        msg = wintypes.MSG()
        try:
            while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312:
                    self.stop_event.set()
                    self.release()
                    break
        finally:
            self.user32.UnregisterHotKey(None, 1)
    def close(self):
        if self.thread_id and self.thread and self.thread.is_alive():
            self.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
            self.thread.join(timeout=2)
