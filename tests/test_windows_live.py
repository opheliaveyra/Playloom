"""All tests use fake input drivers and never inject real keystrokes."""
import threading
import unittest
from unittest.mock import patch, MagicMock
from playloom.core import Action, AgentLoop
from playloom.windows_adapter import WindowsInput, clipped_rect, TargetWindow
from playloom.live import main, wait_for_focus

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
        with patch("playloom.windows_adapter.require_windows"), patch("playloom.windows_adapter.ctypes.WINFUNCTYPE", return_value=lambda fn: fn, create=True):
            with self.assertRaisesRegex(RuntimeError, "found 2"):
                TargetWindow("Test Window", User32())

    def test_terminal_foreground_then_switch_for_preview(self):
        checks = [RuntimeError("terminal focused"), (0, 0, 10, 10)]
        target = MagicMock()
        target.check.side_effect = checks
        wait_for_focus(target, timeout=1, clock=lambda: 0, pause=lambda _: None)
        self.assertEqual(target.check.call_count, 2)

    def test_consent_foreground_then_switch_for_input(self):
        target = MagicMock()
        target.check.side_effect = [RuntimeError("terminal focused"), (0, 0, 10, 10)]
        wait_for_focus(target, timeout=1, stop_event=threading.Event(), clock=lambda: 0, pause=lambda _: None)
        self.assertEqual(target.check.call_count, 2)

    def test_focus_timeout_and_cancel_send_no_keys(self):
        self.target.valid = False
        times = iter([0, 1, 1])
        with self.assertRaisesRegex(RuntimeError, "Timed out"):
            wait_for_focus(self.target, timeout=1, clock=lambda: next(times), pause=lambda _: None)
        self.assertEqual(self.driver.events, [])
        self.stop.set()
        with self.assertRaisesRegex(RuntimeError, "Stopped"):
            wait_for_focus(self.target, stop_event=self.stop)
        self.assertEqual(self.driver.events, [])

    def test_focus_switch_away_after_one_action(self):
        class Capture:
            def __init__(self, target):
                self.target = target
            def screenshot(self):
                self.target.check()
                return b"fake"
        class Policy:
            def decide(self, frame, history):
                return "mock", [Action("right", 0.001)]
        class Recorder:
            def write(self, record):
                pass
        original_wait = self.stop.wait
        def wait(duration):
            self.target.valid = False
            return False
        self.stop.wait = wait
        with self.assertRaises(RuntimeError):
            AgentLoop(Capture(self.target), Policy(), self.inputs, Recorder(), max_steps=2).run()
        self.assertEqual(self.driver.events, [("down", "right"), ("up", "right")])
        self.stop.wait = original_wait

    def test_successful_cli_returns_zero_not_completed_count(self):
        fake_target = MagicMock()
        fake_target.title = "Test Window"
        fake_capture = MagicMock()
        fake_capture.screenshot.return_value = b"png"
        fake_emergency = MagicMock()
        fake_loop = MagicMock()
        fake_loop.run.return_value = 1
        with patch("playloom.live.require_windows"), \
             patch("playloom.live.TargetWindow", return_value=fake_target), \
             patch("playloom.live.WindowsCapture", return_value=fake_capture), \
             patch("playloom.live.WindowsInput", return_value=self.inputs), \
             patch("playloom.live.EmergencyStop", return_value=fake_emergency), \
             patch("playloom.live.AgentLoop", return_value=fake_loop), \
             patch("playloom.live.Recorder"), \
             patch("playloom.live.wait_for_focus"), \
             patch("playloom.live.preview"), \
             patch("builtins.input", return_value="LIVE"):
            self.assertEqual(main(["--live", "--target-title", "Test Window"]), 0)
            fake_loop.run.assert_called_once()
            fake_emergency.start.assert_called_once()
        self.assertEqual(self.driver.events, [])

    def test_f12_registration_failure_prevents_keydown(self):
        fake_target = MagicMock(title="Test Window")
        fake_target.title = "Test Window"
        fake_capture = MagicMock()
        fake_capture.screenshot.return_value = b"png"
        fake_emergency = MagicMock()
        fake_emergency.start.side_effect = RuntimeError("F12 registration failed")
        with patch("playloom.live.require_windows"), patch("playloom.live.TargetWindow", return_value=fake_target), \
             patch("playloom.live.WindowsCapture", return_value=fake_capture), \
             patch("playloom.live.WindowsInput", return_value=self.inputs), \
             patch("playloom.live.EmergencyStop", return_value=fake_emergency), \
             patch("playloom.live.wait_for_focus"), patch("playloom.live.preview"), \
             patch("builtins.input", return_value="LIVE"):
            with self.assertRaisesRegex(RuntimeError, "F12"):
                main(["--live", "--target-title", "Test Window"])
        self.assertEqual(self.driver.events, [])

if __name__ == "__main__":
    unittest.main()
