"""Safe simulation: demonstrates capture -> decide -> act -> record with no game access."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from .core import Action, AgentLoop, Recorder


class FakeCapture:
    def __init__(self):
        self.frame = 0

    def screenshot(self) -> bytes:
        self.frame += 1
        return f"mock-game-frame-{self.frame}".encode()


class DemoPolicy:
    def decide(self, frame: bytes, history: list[dict]):
        moves = ("right", "space", "right", "left", "space")
        return "模拟策略：验证输入和行为日志，不代表视觉 AI。", [Action(moves[len(history) % len(moves)])]


class FakeInput:
    def __init__(self):
        self.events: list[str] = []

    def execute(self, action: Action) -> None:
        self.events.append(action.key)

    def release_all(self) -> None:
        self.events.append("RELEASE_ALL")


def main() -> None:
    # Demo output is intentionally temporary. Your real game/saves are never touched.
    with TemporaryDirectory(prefix="playloom-") as work:
        inputs = FakeInput()
        trace = Path(work) / "actions.jsonl"
        loop = AgentLoop(FakeCapture(), DemoPolicy(), inputs, Recorder(trace), max_steps=5)
        count = loop.run()
        print(f"Playloom v0.1 / DRY-RUN: {count} steps")
        print("Inputs:", ", ".join(inputs.events))
        print("Trace sample:", json.dumps(json.loads(trace.read_text(encoding="utf-8").splitlines()[0]), ensure_ascii=True))
        print("No game access. No save-file access. No API calls.")


if __name__ == "__main__":
    main()