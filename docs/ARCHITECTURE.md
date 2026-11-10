# Playloom 架构研究笔记 / 2026-11-10

## 来源与取舍

- **Cradle** https://github.com/BAAI-Agents/Cradle : `cradle/runner/stardew_runner.py` 中的实际执行链包括 information gathering、self reflection、task inference、skill curation、action planning、skill execute；`cradle/memory/local_memory.py` 用 recent_history + JSON checkpoint。借鉴模块边界，不复制完整复杂依赖。
- **Gamini** https://github.com/yumozi/gamini : `backend/game_loop.py` 负责 video -> inference -> action 循环，录制和推理流水线并发；`backend/input_windows.py` 使用 pydirectinput-rgx；`backend/main.py` 注册 F12 hotkey，提供 WebSocket/UI。借鉴控制闭环与状态推送，不把 Gemini 写死。
- **GameCLI-Agent** https://github.com/BjornBrorsson/GameCLI-Agent : 适合参考多模型连接、动作日志、调试界面，主要针对回合制。
- **computer-use-for-all-agents** https://github.com/Xeakaes/computer-use-for-all-agents : 借鉴 MCP 工具接口、安全门控和窗口控制。

## 设计

```
选定游戏窗口 -> 截图/视频 -> 观察/状态识别 -> 记忆（房间/位置/事件）
                                        |
用户实时指令 -> 大模型策略规划 -----------> 高层动作 -> 动作校验
                                                  |
                      快速本地策略 <- 游戏适配器 <- 执行器
                                                  |
                          截图验证/死亡复盘/事件日志
```

快动作（战斗、闪避）应由本地高频反馈模块承担，不能期待慢速云端 API 每帧决定。

## MVP 顺序

1. 本包 v0.1：**已完成** Python 标准库模拟闭环、动作白名单、动作时长上限、逐步 JSONL、Windows 适配器初稿、4 个测试。Windows 实机尚未测试。
2. v0.2：人工选择游戏窗口；显式开启控制；紧急停止热键 F12 + 确认注册成功；窗口焦点丢失自动停止；先测试记事本/无存档演示游戏（不要真的写入文档）。
3. v0.3：接模型接口（支持 OpenAI-compatible、多模态截图请求）并提供本地 mock 模型；失败时不发送按键；校验 JSON 输出。
4. v0.4：单游戏适配器，包括按键配置、场景判断、死亡检测、关卡图谱；引入 SQLite 持久化。
5. v0.5：网页观看面板；允许人工接管与暂停；指标：成功动作率、每分钟决策次数、死亡原因、单位 API 成本。

## 关于《丝之歌》与原存档

* **本包不会读取、修改或删除任何游戏存档；不会访问游戏路径。**
* 首次实测前，用游戏实际存档位置人工核对备份，设置新的测试存档；不要假定新游戏槽位就足以隔离所有自动写入与设置。
* 测试中关闭不必要的修改器或外部注入，以免难以定位故障。
* 开源仓库只放框架和原创示例，不打包游戏本体、未经许可的资源或第三方 API 密钥。

## 当前原型限制

- `python -m playloom.demo` **只运行模拟策略**，不具备模型视觉推理功能。
- `windows_adapter.py` 未接入主循环的 live CLI；尚缺 Windows 实机测试、系统级紧急停止和权限检查，不能当作可靠的真实游戏自动驾驶程序。
- 安全检查包括键名白名单、单次按键时长上限、每步动作数限制、窗口焦点校验和释放键。并不能替代紧急停止等实机保障。
- 当前无任何实际 API 连接和费用。