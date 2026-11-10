# Playloom 🎮

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