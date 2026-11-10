# Codex 实施任务：Playloom v0.2

目标：在 Windows 上把独立游戏窗口安全接入 `AgentLoop`，允许 **显式用户授权** 的有限自动按键。不要修改任何现有 Steam/《丝之歌》存档，也不要创建任何用户机器上的后台常驻程序。

## 第一步：阅读
1. `README.md`、`docs/ARCHITECTURE.md`、`playloom/core.py`、`playloom/windows_adapter.py`、`tests/test_core.py`。
2. 参考开源 Gamini 的 `backend/game_loop.py`, `input_windows.py`, `main.py`，以及 Cradle 的 `cradle/runner/stardew_runner.py`。不要在许可证不清楚时照搬代码。

## 必需的验收
- 默认运行仍是 dry-run；只有显式传 `--live --target-title <游戏窗口名>` 且二次人工确认才能按键。
- 全局 F12 紧急停止（含正在按住的键），热键注册失败则禁止 live。
- 对每个动作检查 foreground window + title，窗口焦点变化即放弃输入并释放全部键。
- 每次动作限制 <=0.25 秒；控制器在异常、Ctrl+C、终止时释放所有按键；不能只依赖 `asyncio.CancelledError`。
- 至少 8 个模拟测试，不依赖 API、不需要游戏；不得在测试中发送真实键盘事件。
- 默认不保存截图、录屏；仅在用户明确启用时保存诊断帧；不得上传敏感桌面画面。
- 记录模型动作、来源、token/费用（若 API 可获取），并为每个会话添加开销上限。
- 先使用无关紧要的免费小游戏验证，测试通过以后再考虑《丝之歌》。

## 特别说明
- 当前 `WindowsCapture` 与 `WindowsInput` 仅是实验适配器，未真正运行测试。
- 不能宣称 AI 已会玩游戏。v0.2 只验收截图、模拟按键与安全停止；v0.3 才接视觉模型。