# Playloom 🎮

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

Start with a disposable test window or a game with no valuable save data. The CLI selects exactly one visible window with the exact title, captures it, and shows a local in-memory preview. Close the preview, type `LIVE` at the second prompt, then focus the same window. The mock policy sends one short Right press per step; default is one step. F12 is a global emergency stop. Ctrl+C and exceptions release held keys. If F12 cannot be registered, input is disabled. Use `--max-steps N` for more steps (1–100). The session cost ceiling is `--max-cost`; v0.2 has no API calls and records zero tokens/cost. Action metadata goes to `playloom-live-trace.jsonl`; images are never included.

Use `--save-frame frame.png` only if you want one local diagnostic image. No screenshots are stored by default, and no screenshot, video, or save content is uploaded. No API key is needed. Do not run against an existing game save.

Limitations: v0.2 has no vision AI or game-playing ability. The preview uses Tkinter. Capture uses the physical window rectangle clipped to the virtual desktop, including negative monitor origins. Windows DPI awareness and window decorations can affect the captured region; verify the preview before consenting. The Windows live path requires a real Windows disposable-window verification; automated tests use mocks and send no keystrokes.

让 AI 看见游戏、做出决定、操作角色并记住探索经验的实验性开源框架。

**当前版本 v0.1 是可运行的模拟闭环，并非真正 AI 玩家。** 适合交给 Codex 在 Windows 上逐步扩展。

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
- `playloom/windows_adapter.py`：**未验证**的 Windows 截图和按键插件初稿，默认不调用
- `tests/test_core.py`：标准库测试
- `docs/ARCHITECTURE.md`：Cradle/Gamini 源码研究与研发计划
- `docs/CODEX_TASK.md`：给 Codex 的下一阶段任务与验收标准

## 重要限制

Playloom v0.1 **尚未接入大模型，不会直接玩《丝之歌》**，也没有实现系统级紧急停止。切勿在 Windows 上手工拼接并运行 live 循环，先按 `CODEX_TASK.md` 补齐安全机制并实际测试。

## 许可证

本原型由当前工作单独编写，没有复制外部仓库源代码片段。初始使用 MIT 许可证。引用的第三方项目只用于研究，实际复用需逐一核对其许可证。
