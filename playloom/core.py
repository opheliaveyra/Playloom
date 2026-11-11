"""Observable, bounded game-agent loop. No dependencies; demo is simulated."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from threading import Event
import hashlib
import json
import math
import time

KEYS = frozenset({"left", "right", "up", "down", "space", "z", "x", "c", "a", "s", "d", "enter", "esc"})
MAX_DURATION = 0.25  # per action, seconds; long moves need multiple observed steps


@dataclass(frozen=True)
class Action:
    key: str
    duration: float = 0.08

    def __post_init__(self) -> None:
        if self.key not in KEYS:
            raise ValueError(f"Disallowed key: {self.key!r}")
        if not 0 < self.duration <= MAX_DURATION:
            raise ValueError(f"Duration must be in (0, {MAX_DURATION}] seconds")


@dataclass(frozen=True)
class ClickAction:
    """One short left click inside the most recently observed window frame.

    Coordinates are normalized to the captured frame. The 2% inset avoids
    accidentally clicking the desktop or window decorations at its edges.
    """
    x: float
    y: float
    duration: float = 0.06

    def __post_init__(self) -> None:
        for name, value in (("x", self.x), ("y", self.y)):
            if isinstance(value, bool) or not isinstance(value, (float, int)):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(value) or not 0.02 <= value <= 0.98:
                raise ValueError(f"{name} must be between 0.02 and 0.98")
        if isinstance(self.duration, bool) or not isinstance(self.duration, (float, int)):
            raise ValueError("Invalid click duration")
        if not math.isfinite(self.duration) or not 0 < self.duration <= MAX_DURATION:
            raise ValueError("Invalid click duration")


class Capture(Protocol):
    def screenshot(self) -> bytes: ...


class Policy(Protocol):
    def decide(self, frame: bytes, history: list[dict]) -> tuple[str, list[Action | ClickAction]]: ...


class Input(Protocol):
    def execute(self, action: Action | ClickAction) -> None: ...
    def release_all(self) -> None: ...


class Recorder:
    """Append-only decision trace, no raw screen content persisted by default."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class AgentLoop:
    def __init__(self, capture: Capture, policy: Policy, inputs: Input, recorder: Recorder, *, max_steps: int = 5):
        if not 1 <= max_steps <= 100:
            raise ValueError("max_steps must be between 1 and 100")
        self.capture, self.policy, self.inputs, self.recorder = capture, policy, inputs, recorder
        self.max_steps = max_steps
        self.stop_event = Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> int:
        history: list[dict] = []
        completed = 0
        try:
            for step in range(1, self.max_steps + 1):
                if self.stop_event.is_set():
                    break
                frame = self.capture.screenshot()
                reason, actions = self.policy.decide(frame, list(history))
                if self.stop_event.is_set():
                    break
                if len(actions) > 4:
                    raise ValueError("Policy produced too many actions per observation")
                if not all(isinstance(a, (Action, ClickAction)) for a in actions):
                    raise TypeError("Policy actions must be validated Action instances")
                record = {"step": step, "time": time.time(), "frame_sha256": hashlib.sha256(frame).hexdigest(),
                          "reason": reason, "source": type(self.policy).__name__,
                          "tokens": getattr(self.policy, "tokens", 0),
                          "cost": getattr(self.policy, "cost", 0.0),
                          "requests_used": getattr(self.policy, "requests_used", 0),
                          "actions": [
                              {"key": a.key, "duration": a.duration} if isinstance(a, Action)
                              else {"type": "click", "x": a.x, "y": a.y, "duration": a.duration}
                              for a in actions]}
                memory = getattr(self.policy, "memory", None)
                if isinstance(memory, str) and memory:
                    record["memory"] = memory[:400]
                # Record BEFORE execution for inspection and replay.
                self.recorder.write(record)
                for action in actions:
                    if self.stop_event.is_set():
                        break
                    self.inputs.execute(action)
                history.append(record)
                completed += 1
        finally:
            self.inputs.release_all()
        return completed
