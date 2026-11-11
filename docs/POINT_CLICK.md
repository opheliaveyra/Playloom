# Playloom v0.4 · Click / Hybrid Game Input

## Scope

This branch extends the unmerged v0.3 Windows relay path. It does **not**
merge or bypass the v0.2/v0.3 acceptance gates. It has no independent access
to anyone's Windows desktop from this chat.

Playloom can now represent four types of single-step decisions:

| Control mode | Supported decision |
|---|---|
| keyboard | A short bounded key press |
| point-click | One short bounded left mouse click |
| hybrid | One key press, one left click, **or** one key held simultaneously with a left click |
 
The combined action holds an allowed key during the mouse click, then releases
**both** controls even if the target loses focus or F12 is pressed.

This is not yet arbitrary simultaneous WASD + mouse aiming, dragging, right
clicking, mouse wheel, controller input, or automated save isolation. Those
require separate implementation and testing.

## Disposable puzzle acceptance on Windows

Use Python 3.10+ and install optional dependencies:

```powershell
python -m pip install mss pydirectinput-rgx
python -m playloom.disposable_puzzle
```

In a second terminal:

```powershell
python -m playloom.doctor --target-title "Playloom Puzzle Test Window"
python -m playloom.live --live --target-title "Playloom Puzzle Test Window" --policy replay --control-mode point-click --max-steps 1
```

After the preview, explicitly enter `LIVE` and then `MOUSE`; refocus the
puzzle window within 10 seconds. This is an offline fake model click test, not
proof that a real vision AI understands the puzzle. The test room never writes
game saves.

For hybrid offline input, the fake policy holds **Shift while clicking** the center of the test room. The room should display `Hybrid control received: Shift + left mouse click ✓` if both inputs reach it:

```powershell
python -m playloom.live --live --target-title "Playloom Puzzle Test Window" --policy replay --control-mode hybrid --max-steps 1
```

For live vision via a user-controlled OpenAI-compatible relay:

```powershell
python -m playloom.live --live --target-title "Playloom Puzzle Test Window" --policy relay --control-mode hybrid --relay-base-url "https://your-relay.example/v1" --relay-model "your-vision-model" --relay-max-requests 8 --max-steps 8
```

Keep `PLAYLOOM_RELAY_API_KEY` in your local environment or secret manager,
never paste secrets into chat, code or a commit. Remote mode needs **LIVE**,
**UPLOAD** (screenshot disclosure), and **MOUSE** (mouse-input consent).
F12 must register or no action is sent.

Stop with F12 at any time. Close the test window when done.
If the screen content or active window differs from the observed target,
Playloom fails closed.

## Puzzle model response contract

The relay requests exactly one JSON object per screenshot. In hybrid mode:

```json
{"reason":"walk closer","action":"key","key":"right","duration":0.08,"memory":"saw a key"}
```

```json
{"reason":"pick up key","action":"click","x":0.27,"y":0.6,"memory":"key collected"}
```

```json
{"reason":"hold Shift while clicking","action":"key_click","key":"shift","x":0.7,"y":0.5,"duration":0.08,"memory":"door unlocked"}
```

```json
{"reason":"need more information","action":"none","memory":"door locked"}
```

Coordinates are normalized 0..1 relative to the captured window image. The
click target must also lie inside Windows' **client area**, not the title bar
or borders. Mouse duration cannot exceed 0.25 seconds, and each model response
contains only one bounded action. No arbitrary commands or scripts are
executed. Notes are capped at 400 characters; the last three step summaries
are supplied back to the model. The full observation screenshots are not
persisted by default, but relay mode uploads each frame to the configured
provider only after consent. Each request may cost money.

## Important limits

- **Windows interactive keyboard/mouse test remains unverified.** Offline
  unit tests use fakes and never inject real input.
- **Real vision reasoning remains unverified.** No authenticated relay
  endpoint or budget has been provided.
- **Game/save isolation is not implemented.** Do not test a real game
  profile with valuable progress. Start with the bundled disposable room.
- **Point-click** is best for games like Rusty Lake; **hybrid** also allows
  key+mouse titles. More complex games need multi-key hold + mouse movement,
  right click, scrolling, drag and timing primitives, and device tests.
- Test room and replay policy use no network and no existing user save data.
