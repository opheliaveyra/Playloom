# Playloom 🎮

## First: check Windows readiness without spending relay balance

Open the bundled, temporary Playloom test window from the repository root:

```powershell
python -m playloom.disposable_window
```

In a second terminal, run the **read-only doctor**:

```powershell
python -m playloom.doctor
```

The doctor checks optional dependencies, that exactly one test window is open,
and whether F12 can be registered as the emergency stop. It never presses a
key, uploads a screenshot or calls a remote API. A passing doctor does **not**
prove that Windows will receive actual game input. To test one real keyboard
action, run the opt-in offline `--policy replay` command below.

## v0.3 opt-in relay vision

The default policy remains offline mock. A relay must support OpenAI-compatible
Chat Completions with PNG image_url messages and JSON text output. Gemini model
names are supported only if your relay exposes that compatible interface; no
separate official Gemini key is needed. Compatibility with any particular
provider has not been verified.

First open a disposable window in one terminal:

```powershell
python -m playloom.disposable_window
```

In another terminal, test the deterministic offline fake model:

```powershell
python -m playloom.live --live --target-title "Playloom Disposable Test Window" --policy replay
```

Switch to the test window for the preview, close the preview, return to the
terminal and type LIVE, then switch to the test window again. Replay validates a
fake JSON decision through the relay policy and sends one short Right press,
which should move the square. F12 registration must succeed first.

For a single remote request, set PLAYLOOM_RELAY_API_KEY locally in the process
environment using your own secret manager. Never put the key in a command line,
repository, issue, log, or chat. With your relay URL and vision model substituted:

```powershell
python -m playloom.live --live --target-title "Playloom Disposable Test Window" --policy relay --relay-base-url "https://your-relay.example/v1" --relay-model "your-vision-model" --relay-max-requests 1 --max-steps 1
```

Relay mode additionally requires typing UPLOAD after LIVE. That authorizes
sending target screenshots to the displayed endpoint. No remote request happens
before consent and successful F12 registration. Requests have image, response,
output-token, timeout, and attempt limits; failed attempts count too. Redirects
are refused. A stopped or timed-out request cannot produce keyboard input.
Cancellation discards the result immediately; an already-started HTTP operation
may finish in its daemon worker until its transport timeout and cannot retract
an uploaded image. The program never retries automatically.

Request count is displayed and logged. Relay prices and token accounting are
unknown: cost and token fields are null, not a monetary guarantee. The former
mock-only --max-cost option was removed. Inspect your relay's billing separately.
No real relay request or successful interactive Windows/F12 verification has
been performed as part of automated testing. Keep the PR draft until human
verification on a disposable window is complete.

## Windows disposal-window acceptance check

Before trying a game, test input against Playloom's **own dummy window**.
Run two terminals from the repository root:

Terminal A (keep this open):
```powershell
python -m playloom.disposable_window
```
Terminal B (after installing the optional packages listed below):
```powershell
python -m playloom.live --live --target-title "Playloom Disposable Test Window"
```

When prompted, focus the dummy window within 10 seconds; check and close
the preview; type `LIVE` in Terminal B; focus the dummy window again within
10 seconds. It should show **one** Right-arrow key press. The controller sends
a mock action, not a decision from an AI model. For a longer emergency-stop
check, run again with `--max-steps 100` and press F12 while it is running.
Confirm the window stops receiving keys. These manual checks are not replaced
by the automated CI tests.

## v0.2 Windows local preview and mock input

Python 3.10+ is required. The simulation remains dependency free:

```powershell
python -m playloom.demo
python -m unittest discover -s tests -v
```

For the separate Windows live CLI, install optional packages:

```powershell
python -m pip install mss pydirectinput-rgx
python -m playloom.live --live --target-title "Exact Test Window Title"
```

Start with a disposable test window or a game with no valuable save data. The CLI selects exactly one visible window with the exact title. After running the command, switch from the terminal to the target window within 10 seconds. Playloom captures it and shows a local in-memory preview. Close the preview, return to the terminal, type `LIVE`, then switch back to the target within 10 seconds. Each wait times out without sending input. The mock policy sends one short Right press per step; default is one step. F12 is a global emergency stop after consent. Ctrl+C and exceptions release held keys. If F12 cannot be registered, input is disabled. Use `--max-steps N` for more steps (1–100). Mock mode has no API calls and records zero tokens/cost. Action metadata goes to `playloom-live-trace.jsonl`; images are never included.

Use `--save-frame frame.png` only if you want one local diagnostic image. No screenshots are stored by default, and no screenshot, video, or save content is uploaded. No API key is needed. Do not run against an existing game save.

Limitations: v0.2 has no vision AI or game-playing ability. The preview uses Tkinter. Capture uses the physical window rectangle clipped to the virtual desktop, including negative monitor origins. Windows DPI awareness and window decorations can affect the captured region; verify the preview before consenting. The Windows live path requires a real Windows disposable-window verification; automated tests use mocks and send no keystrokes.

让 AI 看见游戏、做出决定、操作角色并记住探索经验的实验性开源框架。

**v0.2 提供可运行的模拟闭环和需人工授权的 Windows mock 控制，并非真正 AI 玩家。**

## 运行（Python 3.10+；无需安装依赖）

在项目根目录执行：

```powershell
python -m playloom.demo
python -m unittest discover -s tests -v
```

模拟流程演示：画面占位数据 → 模拟策略 → 受限制的按键 → 可追踪动作日志 → 释放按键。不会访问任何真实游戏、存档或 API。

## 目录

- `playloom/core.py`：可替换捕获器、策略、执行器，边界校验和模拟执行循环
- `playloom/demo.py`：无依赖安全演示
- `playloom/windows_adapter.py`：Windows 窗口截图、焦点检查、热键与按键插件；仅由独立 live CLI 调用
- `tests/test_core.py`：标准库测试
- `docs/ARCHITECTURE.md`：Cradle/Gamini 源码研究与研发计划
- `docs/CODEX_TASK.md`：给 Codex 的下一阶段任务与验收标准

## 重要限制

Playloom v0.2 **尚未接入大模型，不会直接玩《丝之歌》**。系统级 F12 紧急停止已实现，但当前自动化会话无法完成交互式 Windows 实机验证；使用前请在一次性测试窗口验证。

## 许可证

本原型由当前工作单独编写，没有复制外部仓库源代码片段。初始使用 MIT 许可证。引用的第三方项目只用于研究，实际复用需逐一核对其许可证。
