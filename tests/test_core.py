import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from playloom.core import Action, AgentLoop, Recorder
from playloom.demo import DemoPolicy, FakeCapture, FakeInput


class CoreTests(unittest.TestCase):
    def test_validated_action(self):
        with self.assertRaises(ValueError):
            Action("win")
        with self.assertRaises(ValueError):
            Action("left", 5)
        self.assertEqual(Action("space").key, "space")

    def test_dry_run_and_trace(self):
        with TemporaryDirectory() as work:
            inputs = FakeInput()
            path = Path(work) / "trace.jsonl"
            n = AgentLoop(FakeCapture(), DemoPolicy(), inputs, Recorder(path), max_steps=3).run()
            rows = [json.loads(x) for x in path.read_text(encoding="utf8").splitlines()]
            self.assertEqual(n, 3)
            self.assertEqual([x["step"] for x in rows], [1, 2, 3])
            self.assertEqual(inputs.events, ["right", "space", "right", "RELEASE_ALL"])

    def test_stop_and_release(self):
        with TemporaryDirectory() as work:
            inputs = FakeInput()
            agent = AgentLoop(FakeCapture(), DemoPolicy(), inputs, Recorder(Path(work) / "a.jsonl"))
            agent.stop()
            self.assertEqual(agent.run(), 0)
            self.assertEqual(inputs.events, ["RELEASE_ALL"])

    def test_reject_many_actions(self):
        class BadPolicy:
            def decide(self, frame, history):
                return "bad", [Action("left")] * 5
        with TemporaryDirectory() as work:
            inputs = FakeInput()
            agent = AgentLoop(FakeCapture(), BadPolicy(), inputs, Recorder(Path(work) / "a.jsonl"))
            with self.assertRaises(ValueError):
                agent.run()
            self.assertEqual(inputs.events, ["RELEASE_ALL"])


if __name__ == "__main__":
    unittest.main()