"""Network-free, input-free tests for the Windows diagnostics command."""
from __future__ import annotations

import unittest

from playloom.doctor import diagnose


class Target:
    def __init__(self, title):
        self.title = title

    def check(self):
        raise RuntimeError("terminal currently foreground")


class Stop:
    starts = 0
    closes = 0

    def __init__(self, event, callback):
        self.event = event
        self.callback = callback

    def start(self):
        type(self).starts += 1

    def close(self):
        type(self).closes += 1


class DoctorTests(unittest.TestCase):
    def setUp(self):
        Stop.starts = Stop.closes = 0
        self.messages = []
        self.common = {
            "output": self.messages.append,
            "available": lambda name: object(),
            "require_windows_fn": lambda: None,
            "target_cls": Target,
            "stop_cls": Stop,
        }

    def test_successful_probe_never_performs_input(self):
        self.assertEqual(diagnose(**self.common), 0)
        self.assertEqual((Stop.starts, Stop.closes), (1, 1))
        self.assertTrue(any("No key was pressed" in s for s in self.messages))

    def test_missing_dependency_blocks_hotkey(self):
        params = {**self.common, "available": lambda name: None if name == "mss" else object()}
        self.assertEqual(diagnose(**params), 2)
        self.assertEqual(Stop.starts, 0)

    def test_f12_unavailable_stays_blocked_and_unregistered(self):
        class UnavailableStop(Stop):
            def start(self):
                raise RuntimeError("F12 busy")
        self.assertEqual(diagnose(**{**self.common, "stop_cls": UnavailableStop}), 2)
        self.assertEqual(Stop.closes, 1)

    def test_target_missing_prevents_f12_probe(self):
        def missing(_title):
            raise RuntimeError("Window not found")
        self.assertEqual(diagnose(**{**self.common, "target_cls": missing}), 2)
        self.assertEqual(Stop.starts, 0)


if __name__ == "__main__":
    unittest.main()
