"""Opt-in Windows control with mock, offline replay, or explicit remote vision."""
from __future__ import annotations
import argparse
import base64
import time
import os
import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from .core import Action, AgentLoop, Recorder
from .windows_adapter import EmergencyStop, TargetWindow, WindowsCapture, WindowsInput, require_windows
from .relay import RelayConfig, RelayVisionPolicy

class MockPolicy:
    def decide(self, frame, history):
        return "mock policy: one short right press", [Action("right", 0.08)]

def wait_for_focus(target, *, timeout=10.0, stop_event=None, clock=None, pause=None):
    """Give the user time to select the target; never move focus or send input."""
    clock = clock or time.monotonic
    pause = pause or time.sleep
    deadline = clock() + timeout
    while True:
        if stop_event is not None and stop_event.is_set():
            raise RuntimeError("Stopped while waiting for target focus")
        try:
            target.check()
            return
        except RuntimeError:
            if clock() >= deadline:
                raise RuntimeError("Timed out waiting for target window focus")
            pause(min(0.1, max(0, deadline - clock())))

def preview(png):
    """Show the in-memory capture locally; no frame is written by default."""
    import tkinter as tk
    root = tk.Tk()
    root.title("Playloom local capture preview (close to continue)")
    photo = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
    label = tk.Label(root, image=photo)
    label.pack()
    root.mainloop()

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--target-title")
    parser.add_argument("--save-frame", type=Path, help="Opt in to saving one diagnostic PNG")
    parser.add_argument("--max-steps", type=int, default=1)
    parser.add_argument("--policy", choices=("mock", "replay", "relay"), default="mock")
    parser.add_argument("--control-mode", choices=("keyboard", "point-click", "hybrid"), default="keyboard",
                        help="Point-click requires a separate MOUSE confirmation")
    parser.add_argument("--relay-base-url")
    parser.add_argument("--relay-model")
    parser.add_argument("--relay-max-requests", type=int)
    args = parser.parse_args(argv)
    if not args.live or not args.target_title:
        parser.error("Input requires both --live and --target-title")
    if not 1 <= args.max_steps <= 100:
        parser.error("--max-steps must be between 1 and 100")
    if args.control_mode in ("point-click", "hybrid") and args.policy == "mock":
        parser.error("Point-click mode requires --policy replay or --policy relay")
    config = None
    if args.policy == "relay":
        try:
            config = RelayConfig(args.relay_base_url or "", args.relay_model or "",
                                 os.environ.get("PLAYLOOM_RELAY_API_KEY", ""),
                                 max_requests=args.relay_max_requests or 0)
        except (ValueError, TypeError):
            parser.error("Relay requires a valid URL, model, PLAYLOOM_RELAY_API_KEY, and request cap (1–100)")
    require_windows()
    target = TargetWindow(args.target_title)
    capture = WindowsCapture(target)
    print(f"Switch to {target.title!r} within 10 seconds for the local preview.")
    wait_for_focus(target)
    frame = capture.screenshot()
    if args.save_frame:
        args.save_frame.write_bytes(frame)
    preview(frame)
    print(f"Selected window: {target.title!r}. Policy: {args.policy}. F12 stops all input.")
    if input("Type LIVE to allow input to this window: ").strip() != "LIVE":
        print("Consent declined.")
        return 0
    stop = Event()
    policy = MockPolicy()
    if config is not None:
        print(f"Remote policy uploads target screenshots to {config.endpoint}. "
              f"Maximum attempts: {config.max_requests}. Monetary cost is unknown.")
        if input("Type UPLOAD to consent to screenshots leaving this PC: ").strip() != "UPLOAD":
            print("Remote upload declined.")
            return 0
        policy = RelayVisionPolicy(replace(config, allow_remote=True), stop_event=stop, control_mode=args.control_mode)
    elif args.policy == "replay":
        config = RelayConfig("https://offline.invalid", "replay", "fake-only",
                             allow_remote=True, max_requests=args.max_steps)
        def fake_transport(req, timeout):
            decision = ({"reason": "offline click replay", "action": "click",
                         "x": 0.5, "y": 0.55, "memory": "Test window clicked"}
                        if args.control_mode in ("point-click", "hybrid") else
                        {"reason": "offline replay", "key": "right", "duration": 0.08})
            return json.dumps({"choices": [{"message": {"content": json.dumps(decision)}}]}).encode()
        policy = RelayVisionPolicy(config, transport=fake_transport, stop_event=stop,
                                   control_mode=args.control_mode)
    if args.control_mode in ("point-click", "hybrid"):
        print("Mouse control moves the pointer and clicks inside the observed target window.")
        if input("Type MOUSE to allow left clicks in this window: ").strip() != "MOUSE":
            print("Mouse consent declined.")
            return 0
    inputs = WindowsInput(target, stop, frame_source=capture,
                          allow_mouse=args.control_mode in ("point-click", "hybrid"))
    emergency = EmergencyStop(stop, inputs.release_all)
    try:
        emergency.start()
        print(f"Switch back to {target.title!r} within 10 seconds. F12 cancels.")
        wait_for_focus(target, stop_event=stop)
        # Trace contains only action metadata and a frame hash, never image bytes.
        recorder = Recorder(Path("playloom-live-trace.jsonl"))
        loop = AgentLoop(capture, policy, inputs, recorder, max_steps=args.max_steps)
        loop.stop_event = stop
        completed = loop.run()
        print(f"Completed {completed} observation step(s).")
        return 0
    except KeyboardInterrupt:
        stop.set()
        print("Stopped by Ctrl+C.")
        return 130
    finally:
        stop.set()
        inputs.release_all()
        emergency.close()
        if isinstance(policy, RelayVisionPolicy):
            print(f"Requests attempted: {policy.requests_used}/{policy.config.max_requests}. "
                  "Remote monetary cost is unknown." if args.policy == "relay" else
                  f"Offline replay requests: {policy.requests_used}; no network used.")

if __name__ == "__main__":
    raise SystemExit(main())
