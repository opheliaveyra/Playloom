"""Point-and-click checks. Every test uses fake windows, drivers and relay responses."""
from __future__ import annotations

import json
import math
import threading
import unittest
from unittest.mock import MagicMock, patch

from playloom.core import Action, AgentLoop, ClickAction, KeyClickAction
from playloom.live import main
from playloom.relay import RelayConfig, RelayVisionPolicy
from playloom.windows_adapter import WindowsInput

PNG = b"\x89PNG\r\n\x1a\n" + b"not-a-real-frame"


def response(data):
    return json.dumps({"choices": [{"message": {"content": json.dumps(data)}}]}).encode()


def policy(transport):
    config = RelayConfig("https://fake.invalid/v1", "test-vision", "fake-key",
                         allow_remote=True, max_requests=4)
    return RelayVisionPolicy(config, transport=transport, control_mode="point-click")


class FakeTarget:
    def __init__(self):
        self.visible = True
        self.rect = (0, 0, 200, 100)

    def check(self):
        if not self.visible:
            raise RuntimeError("focus lost")
        return self.rect


class FakeDriver:
    def __init__(self):
        self.events = []
        self.fail_down = False

    def moveTo(self, x, y):
        self.events.append(("move", x, y))

    def mouseDown(self, *, button):
        self.events.append(("down", button))
        if self.fail_down:
            raise RuntimeError("injected driver failure")

    def mouseUp(self, *, button):
        self.events.append(("up", button))

    def keyDown(self, key):
        self.events.append(("keyDown", key))

    def keyUp(self, key):
        self.events.append(("keyUp", key))


class ClickValidationTests(unittest.TestCase):
    def test_valid_coordinates(self):
        click = ClickAction(.2, .7)
        self.assertEqual((click.x, click.y), (.2, .7))

    def test_simultaneous_combo_is_validated(self):
        combo = KeyClickAction("shift", .3, .7, .04)
        self.assertEqual((combo.key, combo.x, combo.y), ("shift", .3, .7))
        for key in ("enter", "esc", "win", "alt"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                KeyClickAction(key, .5, .5)
        with self.assertRaises(ValueError):
            KeyClickAction("shift", -1, .3)

    def test_reject_bad_coordinates(self):
        for x, y in ((0, .5), (1, .5), (-.1, .5), (float("nan"), .5),
                     (float("inf"), .5), (True, .5), ("0.5", .5), (.5, None)):
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                ClickAction(x, y)

    def test_reject_long_or_invalid_click(self):
        for duration in (0, -.1, 3, True, float("nan")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                ClickAction(.5, .5, duration)

    def test_agent_records_normalized_click_without_image_data(self):
        class FakePolicy:
            memory = "Found the key"
            def decide(self, frame, history):
                return "click key", [ClickAction(.5, .5)]
        records = []
        inputs = MagicMock()
        capture = MagicMock()
        capture.screenshot.return_value = b"frame"
        recorder = MagicMock()
        recorder.write.side_effect = records.append
        self.assertEqual(AgentLoop(capture, FakePolicy(), inputs, recorder).run(), 5)
        self.assertEqual(records[0]["actions"][0]["type"], "click")
        self.assertEqual(records[0]["memory"], "Found the key")
        self.assertNotIn(b"frame", str(records).encode())
        inputs.release_all.assert_called_once()


class MouseDriverTests(unittest.TestCase):
    def setUp(self):
        self.target, self.driver, self.stop = FakeTarget(), FakeDriver(), threading.Event()
        self.frame = MagicMock()
        self.frame.last_window_rect = self.target.rect
        self.frame.last_client_rect = (0, 0, 200, 100)
        self.frame.last_frame_rect = {"left": 0, "top": 0, "width": 200, "height": 100}
        self.inputs = WindowsInput(self.target, self.stop, self.driver,
                                   frame_source=self.frame, allow_mouse=True)

    def test_click_maps_to_observed_frame_and_releases(self):
        self.inputs.execute(ClickAction(.5, .5, .001))
        self.assertEqual(self.driver.events, [("move", 100, 50), ("down", "left"), ("up", "left")])

    def test_key_held_during_click_and_both_released(self):
        self.inputs.execute(KeyClickAction("shift", .5, .5, .001))
        self.assertEqual(self.driver.events, [
            ("keyDown", "shift"), ("move", 100, 50), ("down", "left"),
            ("up", "left"), ("keyUp", "shift")])

    def test_client_area_excludes_system_titlebar(self):
        self.frame.last_client_rect = (0, 30, 200, 100)
        with self.assertRaisesRegex(RuntimeError, "client area"):
            self.inputs.execute(ClickAction(.5, .1))
        self.assertEqual(self.driver.events, [])

    def test_key_click_releases_on_stop(self):
        def stopped(_seconds):
            self.stop.set()
            return True
        self.stop.wait = stopped
        with self.assertRaisesRegex(RuntimeError, "Emergency"):
            self.inputs.execute(KeyClickAction("shift", .5, .5))
        self.assertEqual(self.driver.events[-2:], [("up", "left"), ("keyUp", "shift")])

    def test_mouse_disabled_by_default(self):
        inputs = WindowsInput(self.target, self.stop, self.driver, frame_source=self.frame)
        with self.assertRaisesRegex(RuntimeError, "opt-in"):
            inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events, [])

    def test_no_capture_no_input(self):
        self.frame.last_frame_rect = None
        with self.assertRaisesRegex(RuntimeError, "fresh"):
            self.inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events, [])

    def test_moving_window_before_click_fails_closed(self):
        self.target.rect = (10, 0, 210, 100)
        with self.assertRaisesRegex(RuntimeError, "moved"):
            self.inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events, [])

    def test_focus_lost_prevents_mouse_input(self):
        self.target.visible = False
        with self.assertRaisesRegex(RuntimeError, "focus"):
            self.inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events, [])

    def test_stop_before_click_prevents_mouse_input(self):
        self.stop.set()
        self.inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events, [])

    def test_failed_mouse_down_releases(self):
        self.driver.fail_down = True
        with self.assertRaises(RuntimeError):
            self.inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events[-1], ("up", "left"))

    def test_f12_stop_during_click_releases(self):
        def stopped(_seconds):
            self.stop.set()
            return True
        self.stop.wait = stopped
        with self.assertRaisesRegex(RuntimeError, "Emergency"):
            self.inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events[-1], ("up", "left"))

    def test_focus_lost_during_click_releases(self):
        def change_focus(_seconds):
            self.target.visible = False
            return False
        self.stop.wait = change_focus
        with self.assertRaisesRegex(RuntimeError, "focus"):
            self.inputs.execute(ClickAction(.5, .5))
        self.assertEqual(self.driver.events[-1], ("up", "left"))


class PuzzlePolicyTests(unittest.TestCase):
    def test_vision_click_and_memory_carry_to_next_frame(self):
        requests = []
        def fake(req, timeout):
            requests.append(json.loads(req.data))
            return response({"reason": "Pick up the brass key", "action": "click",
                             "x": .31, "y": .62, "memory": "The key lies on the left."})
        p = policy(fake)
        reason, moves = p.decide(PNG, [])
        self.assertEqual(reason, "Pick up the brass key")
        self.assertEqual(len(moves), 1)
        self.assertIsInstance(moves[0], ClickAction)
        self.assertEqual(moves[0].x, .31)
        self.assertEqual(p.memory, "The key lies on the left.")
        p.decide(PNG, [])
        text = requests[1]["messages"][1]["content"][0]["text"]
        self.assertIn("The key lies on the left.", text)
        self.assertIn("image/png;base64,", requests[1]["messages"][1]["content"][1]["image_url"]["url"])

    def test_hybrid_model_can_decide_key_click_and_combo(self):
        config = RelayConfig("https://fake.invalid/v1", "test-vision", "fake-key",
                             allow_remote=True, max_requests=4)
        decisions = iter([
            {"reason":"walk","action":"key","key":"right","duration":.08,"memory":"walked"},
            {"reason":"inspect","action":"click","x":.4,"y":.7,"memory":"button"},
            {"reason":"hold + click","action":"key_click","key":"shift","x":.6,
             "y":.6,"duration":.08,"memory":"door"},
            {"reason":"stop","action":"none","memory":"done"}
        ])
        p = RelayVisionPolicy(config, transport=lambda req, t: response(next(decisions)),
                              control_mode="hybrid")
        self.assertIsInstance(p.decide(PNG, [])[1][0], Action)
        self.assertIsInstance(p.decide(PNG, [])[1][0], ClickAction)
        self.assertIsInstance(p.decide(PNG, [])[1][0], KeyClickAction)
        self.assertEqual(p.decide(PNG, []), ("stop", []))
        self.assertEqual(p.memory, "done")

    def test_abstain_and_retained_memory(self):
        p = policy(lambda req, timeout: response({"reason": "Need clue", "action": "none",
                                                   "memory": "Door is locked"}))
        self.assertEqual(p.decide(PNG, []), ("Need clue", []))
        self.assertEqual(p.memory, "Door is locked")

    def test_invalid_model_clicks_never_reach_driver(self):
        malformed = [
            {"reason": "out of range", "action": "click", "x": 9, "y": .5},
            {"reason": "nan", "action": "click", "x": float("nan"), "y": .5},
            {"reason": "boolean", "action": "click", "x": True, "y": .5},
            {"reason": "wrong", "action": "click", "x": .5, "y": .5, "url": "https://bad"},
            {"reason": "wrong", "action": "shell", "code": "dir"},
            {"reason": "wrong", "action": "none", "x": .5},
            {"reason": "wrong", "action": "none", "memory": 123},
            {"reason": "wrong", "action": "click", "x": .5, "y": .5, "memory": "x" * 401},
        ]
        for decision in malformed:
            with self.subTest(decision=decision):
                p = policy(lambda req, t, value=decision: response(value))
                reason, actions = p.decide(PNG, [])
                self.assertEqual(actions, [])
                self.assertEqual(p.memory, "")

    def test_click_mode_requires_separate_mouse_consent(self):
        with patch("playloom.live.require_windows"), \
             patch("playloom.live.TargetWindow"), patch("playloom.live.WindowsCapture"), \
             patch("playloom.live.preview"), patch("playloom.live.wait_for_focus"), \
             patch("playloom.live.WindowsInput") as inputs, \
             patch("builtins.input", side_effect=["LIVE", "not MOUSE"]):
            self.assertEqual(main(["--live", "--target-title", "Test Window", "--policy", "replay",
                                   "--control-mode", "point-click"]), 0)
            inputs.assert_not_called()

    def test_hybrid_requires_separate_mouse_consent(self):
        with patch("playloom.live.require_windows"), \
             patch("playloom.live.TargetWindow"), patch("playloom.live.WindowsCapture"), \
             patch("playloom.live.preview"), patch("playloom.live.wait_for_focus"), \
             patch("playloom.live.WindowsInput") as inputs, \
             patch("builtins.input", side_effect=["LIVE", "not MOUSE"]):
            self.assertEqual(main(["--live", "--target-title", "Test Window",
                                   "--policy", "replay", "--control-mode", "hybrid"]), 0)
            inputs.assert_not_called()

    def test_mock_policy_cannot_enable_mouse(self):
        with self.assertRaises(SystemExit):
            main(["--live", "--target-title", "Test Window", "--control-mode", "point-click"])


if __name__ == "__main__":
    unittest.main()
