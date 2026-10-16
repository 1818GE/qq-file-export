---
name: qq-file-export
description: "用户说『我在 QQ 发了个文件』『从 QQ 下载这个文件』『把 QQ 收到的文件拿下来』『QQ 文件另存为』『导出 QQ 文件』『读取 QQ 发来的文件』『QQ 里那个 srt / pdf / 压缩包』时触发：把 QQ 收到的文件另存到本地，详见 references/sop.md。"
version: 1.0.0
metadata:
  default-enabled: true
---

# 从 QQ 获取文件到本地

## 这条链路解决什么

用户通过 QQ 发来的文件，**不经过任何"传输接口"，而是先落在本机 QQ 客户端里**。本技能用 `windows-mcp` 做 GUI 自动化，把它"另存为"到本地工作区，再读取内容。

**依赖**：`windows-mcp` 连接器 running（20 工具）+ 本机 QQ 客户端已登录。

## 不应触发（near-miss）

以下说法落在 QQ 的其它能力上，**不应触发本技能**：

- 「QQ 好友申请怎么处理」「怎么加 QQ 好友」→ 社交管理，不是文件导出。
- 「怎么撤回刚才那条 QQ 消息」→ 消息操作，本技能只读不改。
- 「把 QQ 聊天记录导出成表格」→ 历史消息检索，走消息库解密链路，不是 GUI 另存为。
- 「QQ 表情包怎么保存」→ 客户端资源保存，与文件消息不同。

## 前置检查

1. `windows-mcp` 连接器状态 **running**（20 个工具）——动手前先查状态。
2. QQ 进程在跑、`MainWindowTitle` 非空；否则先启动 QQ 并登录。
3. 目标文件**已接收完成**——仍在传输的气泡右键没有「另存为」。
4. （可选）GUI 看不清文件名/大小时，先在消息库定位：`40800` 里 field `45405` = 文件字节数、field `45402` = 文件名；库 `<QQ_DATA_DIR>\nt_qq\nt_db\nt_msg.db`（本机示例），表 `c2c_msg_table` / `group_msg_table`。

## 安全检查清单

- [ ] **只读操作**：不转发、不删除、不撤回 QQ 内任何内容。
- [ ] **重启先告知**：重启 QQ 前先告知用户「将短暂关闭 QQ 客户端并自动重登」。
- [ ] **不误覆盖**：另存为前确认目标路径没有同名旧文件。
- [ ] **落盘合规**：存进工作区对应目录，不落系统临时目录。
- [ ] **来源登记**：非公开渠道来源的，在文件名或台账里标注来源性质。
- [ ] **大文件核对**：超过 100 MB 的，落盘后核对字节数，防传输中断导致残缺。

## 完整流程（七步）

### 0. 判断 QQ 主面板是否"僵尸"（最关键）

**症状**：会话列表陈旧（和右侧聊天对不上）+ 面板内点击/输入全无响应 + `snapshot` 的 UI 树里 `window "QQ"` 无子元素。

**对策**：**重启 QQ 进程**（QQ 记住登录态，重启后自动重登）：

> ⚠️ **重启前先告知用户**：将短暂关闭 QQ 客户端并自动重登；若检测到文件正在传输，等接收完成再操作。

```powershell
$exe = (Get-Process QQ | Select-Object -First 1).Path   # 本机为 <QQ_EXE_PATH>（本机示例）
Get-Process QQ -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 4
Start-Process $exe
```

重启后列表刷新、UI 树可读、点击恢复。

### 1. 看屏

`windows-mcp_snapshot(use_vision=True)`。记住：**UI 树里会给出元素的屏幕坐标，直接拿来做 `loc` 最稳。**

### 2. 把 QQ 切前台

优先用 Python `win32gui`（`ShowWindow(SW_RESTORE)` + `SetForegroundWindow`），比 `app(mode="switch")` 可靠（后者常报 `Application Qq not found`）。窗口特征：`class=Chrome_WidgetWin_1`，`title="QQ"`。

### 3. 搜索会话

用 **坐标**，不要用 label：

```
windows-mcp_type(loc=[<搜索框坐标>], text="<对方QQ号>")
windows-mcp_wait(duration=1)
windows-mcp_snapshot(use_vision=True)   # 拿搜索结果项坐标
```

> ⚠️ `windows-mcp_click/type` 的 `label` 参数只接受**数字 id**，传元素文本会报 `int_parsing`。**统一用 `loc=[x,y]`。**

### 4. 打开会话

`windows-mcp_click(loc=[<搜索结果项坐标>], clicks=1)` → `snapshot` 确认右侧切到目标会话。

### 5. 定位文件气泡

`snapshot` + 必要时 `scroll`。要精确时，用 PowerShell 的 `System.Drawing.CopyFromScreen` 裁剪卡片附近区域读图，毫米级确认坐标。

### 6. 右键 → 另存为

```
windows-mcp_click(loc=[<卡片坐标>], button="right", clicks=1)
windows-mcp_wait(duration=1)
windows-mcp_snapshot(use_vision=True)      # 看菜单
windows-mcp_click(loc=[<另存为 坐标>], clicks=1)
windows-mcp_wait(duration=2)
```

### 7. 填路径保存

**整段绝对路径走剪贴板**（中文/空格不丢）：

```
windows-mcp_clipboard(mode="set", text="<WORKSPACE>\\文件名.ext")
windows-mcp_click(loc=[<文件名框坐标>], clicks=1)
windows-mcp_shortcut(shortcut="ctrl+a")
windows-mcp_shortcut(shortcut="ctrl+v")
windows-mcp_shortcut(shortcut="enter")
```

> 示例里的保存目录 `<WORKSPACE>\`（本机示例）按用户实际工作区替换。

## 验证（必做）

1. `Get-Item <路径> | Select Name,Length,LastWriteTime`
2. **与消息里记录的字节数对一下**：QQ 消息 protobuf（`40800`）里 field **45405** 的 varint 就是文件字节数（例：srt=103,281）
3. 打开/读取确认内容

## 关键坑

| 坑 | 对策 |
|---|---|
| 僵尸面板（列表陈旧+点击失灵+UI树空） | **重启 QQ 进程**（先告知用户） |
| `label` 传文本报错 | 改用坐标 `loc=[x,y]` |
| 另存为落到"上次目录" | 用完整路径覆盖"文件名"框 |
| 中文/空格被截断 | 整段路径走剪贴板粘贴 |
| 右键误触 Edge 菜单 | 先 snapshot 确认菜单来源 |
| 文件传输未完成 | 等接收完再右键（否则无"另存为"） |

## 不成立的通道（别浪费时间）

- **CDN 直连**：文件消息的 `40800` **不含**下载 URL/rkey（只有图片消息内嵌 `multimedia.nt.qq.com.cn/download?...&rkey=...`）。即使从 QQ 进程内存扫到 rkey，配消息里的 `D6EA...` 串请求也返回 `invalid fileid`。**文件只能走 GUI。**
- **纯命令行通道**：目前判断不存在。

## 相关资产

- 完整 SOP（逐字副本，含前置检查、坐标链路、已知坑清单）：`references/sop.md`
- 消息库解密技能：`qq-nt-decrypt`（用于先定位消息 / 核对文件名与字节数）
- 工作目录：`<WORK_DIR>\`（本机示例；一次性脚本、debug 图）
