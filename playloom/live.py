"""Separate Windows live CLI. The policy is fixed and contains no AI or network access."""
from __future__ import annotations
import argparse
import base64
import time
from pathlib import Path
from threading import Event
from .core import Action, AgentLoop, Recorder
from .windows_adapter import EmergencyStop, TargetWindow, WindowsCapture, WindowsInput, require_windows

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
    parser.add_argument("--max-cost", type=float, default=0.0, help="Session API cost ceiling; v0.2 uses zero API calls")
    args = parser.parse_args(argv)
    if not args.live or not args.target_title:
        parser.error("Input requires both --live and --target-title")
    if args.max_cost < 0:
        parser.error("--max-cost must be nonnegative")
    require_windows()
    target = TargetWindow(args.target_title)
    capture = WindowsCapture(target)
    print(f"Switch to {target.title!r} within 10 seconds for the local preview.")
    wait_for_focus(target)
    frame = capture.screenshot()
    if args.save_frame:
        args.save_frame.write_bytes(frame)
    preview(frame)
    print(f"Selected window: {target.title!r}. F12 stops all input. Mock policy presses Right for 0.08 seconds.")
    if input("Type LIVE to allow input to this window: ").strip() != "LIVE":
        print("Consent declined.")
        return 0
    stop = Event()
    inputs = WindowsInput(target, stop)
    emergency = EmergencyStop(stop, inputs.release_all)
    try:
        emergency.start()
        print(f"Switch back to {target.title!r} within 10 seconds. F12 cancels.")
        wait_for_focus(target, stop_event=stop)
        # Trace contains only action metadata and a frame hash, never image bytes.
        recorder = Recorder(Path("playloom-live-trace.jsonl"))
        loop = AgentLoop(capture, MockPolicy(), inputs, recorder, max_steps=args.max_steps)
        loop.stop_event = stop
        completed = loop.run()
        print(f"Completed {completed} mock action step(s).")
        return 0
    except KeyboardInterrupt:
        stop.set()
        print("Stopped by Ctrl+C.")
        return 130
    finally:
        stop.set()
        inputs.release_all()
        emergency.close()

if __name__ == "__main__":
    raise SystemExit(main())
