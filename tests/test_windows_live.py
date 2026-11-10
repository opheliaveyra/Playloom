"""All tests use fake input drivers and never inject real keystrokes."""
import threading
import unittest
from unittest.mock import patch
from playloom.core import Action
from playloom.windows_adapter import WindowsInput, clipped_rect, TargetWindow
from playloom.live import main

class Target:
    def __init__(self):
        self.valid = True
    def check(self):
        if not self.valid:
            raise RuntimeError("focus lost")
        return (0, 0, 100, 100)

class Driver:
    def __init__(self):
        self.events = []
        self.fail = False
    def keyDown(self, key):
        self.events.append(("down", key))
        if self.fail:
            raise RuntimeError("driver failed")
    def keyUp(self, key):
        self.events.append(("up", key))

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.target, self.driver, self.stop = Target(), Driver(), threading.Event()
        self.inputs = WindowsInput(self.target, self.stop, self.driver)

    def test_focus_loss_prevents_input(self):
        self.target.valid = False
        with self.assertRaises(RuntimeError):
            self.inputs.execute(Action("right"))
        self.assertEqual(self.driver.events, [])

    def test_stopped_prevents_input(self):
        self.stop.set()
        self.inputs.execute(Action("right"))
        self.assertEqual(self.driver.events, [])

    def test_normal_press_releases(self):
        self.inputs.execute(Action("right", 0.001))
        self.assertEqual(self.driver.events, [("down", "right"), ("up", "right")])

    def test_driver_exception_releases(self):
        self.driver.fail = True
        with self.assertRaises(RuntimeError):
            self.inputs.execute(Action("right"))
        self.assertEqual(self.driver.events[-1], ("up", "right"))

    def test_emergency_stop_releases_held_key(self):
        def wait(_):
            self.stop.set()
            return True
        self.stop.wait = wait
        with self.assertRaisesRegex(RuntimeError, "Emergency"):
            self.inputs.execute(Action("right"))
        self.assertEqual(self.driver.events[-1], ("up", "right"))

    def test_focus_loss_after_press_releases(self):
        def wait(_):
            self.target.valid = False
            return False
        self.stop.wait = wait
        with self.assertRaises(RuntimeError):
            self.inputs.execute(Action("right"))
        self.assertEqual(self.driver.events[-1], ("up", "right"))

    def test_reject_unvalidated_input(self):
        with self.assertRaises(TypeError):
            self.inputs.execute("right")
        self.assertEqual(self.driver.events, [])

    def test_clips_offscreen_rect(self):
        monitor = [{"left": -100, "top": 0, "width": 200, "height": 100}]
        self.assertEqual(clipped_rect((-120, -10, 20, 50), monitor),
                         {"left": -100, "top": 0, "width": 120, "height": 50})

    def test_fully_offscreen_rejected(self):
        with self.assertRaises(RuntimeError):
            clipped_rect((200, 0, 300, 50), [{"left": 0, "top": 0, "width": 100, "height": 100}])

    def test_cli_requires_both_opt_in_flags(self):
        with self.assertRaises(SystemExit):
            main(["--live"])
        with self.assertRaises(SystemExit):
            main(["--target-title", "Test Window"])

    def test_exact_window_match_requires_uniqueness(self):
        class User32:
            def EnumWindows(self, callback, _):
                callback(1, 0)
                callback(2, 0)
                return True
            def IsWindowVisible(self, hwnd):
                return True
            def GetWindowTextLengthW(self, hwnd):
                return 11
            def GetWindowTextW(self, hwnd, buf, size):
                buf.value = "Test Window"
        with patch("playloom.windows_adapter.require_windows"), patch("playloom.windows_adapter.ctypes.WINFUNCTYPE", return_value=lambda fn: fn):
            with self.assertRaisesRegex(RuntimeError, "found 2"):
                TargetWindow("Test Window", User32())

if __name__ == "__main__":
    unittest.main()
