# 从 QQ 获取文件的详细操作方法（SOP）

> **用途**：把用户通过 QQ 发来的文件（PDF / 压缩包 / 文档 / 字幕 / 图片等），从 QQ 客户端导出到本地工作区。
> **实战案例**
> - 案例日期一：导出《示例文档.pdf》（<AUTHOR>主编）扫描版 PDF，18,138,636 字节
> - 案例日期二：导出「示例字幕.srt」字幕，103,281 字节（补齐「僵尸面板」「坐标点击」「大小核对」三条经验）
> **依赖**：windows-mcp 连接器（本机 GUI 自动化）+ QQ 客户端在本机运行
> **版本**：v1.1

---

## 〇、一句话原理

**文件不是"传输"给我的，而是先落在你的 QQ 客户端里，我再通过本机 GUI 自动化（点击 + 右键另存为）把它拷出来。**

这条通道依赖三件事同时成立：
1. QQ 客户端在本机运行且已登录
2. 目标文件已经**接收完成**（在会话记录里可见）
3. QQ 主面板处于**健康状态**（不是"僵尸面板"，见第二章 0 步），且 GUI 自动化能正常操作它

---

## 一、前置检查（动手机之前）

### 1. 确认连接器在线

调用 `mcp_connectors_status`，确认：

| 连接器 | 要求状态 | 工具数 |
|---|---|---|
| `windows-mcp` | **running** | 20 |

**若 stopped**：先让 mcp-keepalive 重连（30 秒一轮自动检查）；仍不行则走第五章的降级方案。

### 2. 确认 QQ 进程在跑

用 `windows-mcp_powershell` 执行：

```powershell
Get-Process | Where-Object { $_.ProcessName -like "*QQ*" } | Select-Object ProcessName, Id, MainWindowTitle
```

**期望**：至少一个进程，且 `MainWindowTitle` 不为空。
**若为空或查不到**：需要先启动 QQ 并登录（见第三章 3.2）。

### 3.（可选，更稳）先在消息库里定位目标消息

如果 GUI 一时看不清文件名 / 大小，可先解密 QQ 消息库确认（方法见 `qq-nt-decrypt` 技能）：

- 库：`<QQ_DATA_DIR>\nt_qq\nt_db\nt_msg.db`（SQLCipher，头 1024 字节）
- 表：`c2c_msg_table`（私聊）/ `group_msg_table`（群）
- 键列：`40030`=对方号，`40058`=日期时间戳，`40050`=发送时间戳，`40003`=序号，`40800`=protobuf 内容
- **文件大小**：`40800` 里 field `45405` 的 varint 值就是**文件字节数**（本次 103,281 ↔ QQ 显示 100.86 KB，可用于落盘后核对）
- **文件名**：`40800` 里 field `45402` 的 UTF-8 字符串

> 说明：文件消息的 `40800` **不含下载 URL / rkey**（只有**图片**消息才内嵌 `multimedia.nt.qq.com.cn/download?appid=...&fileid=...&rkey=...`）。所以**不要**试图直接拼 CDN 链接下载，走 GUI 另存为。

---

## 二、主流程（七步）

### 步骤 0 · 判断 QQ 主面板是否"僵尸"（新增，最重要）

**症状**（本次踩坑）：
- 会话列表**陈旧**（最新只到几天前，右侧聊天内容却和左侧列表对不上）
- 面板里的**点击、双击、输入全部无响应**（但任务栏、开始菜单等系统窗口响应正常）
- `windows-mcp` 的 UI 树里 `window "QQ"` **没有子元素**（accessibility 拿不到）

**判定**：出现以上任意组合，即"僵尸面板"。

**对策**：**重启 QQ 进程**（QQ 会记住登录，重启后自动登录）：

```powershell
$exe = (Get-Process QQ | Select-Object -First 1).Path
Get-Process QQ -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 4
Start-Process $exe
```

本机 QQ 路径：`<QQ_EXE_PATH>`

**重启后的预期**：会话列表刷新到最新（目标会话出现在最前）、UI 树里能看到按钮/编辑框/会话项、点击恢复有效。

> ⚠️ 说明：QQ 主面板的异常不止"白屏"一种，**列表陈旧 + 点击失灵 + UI 树为空**同样是异常表现，处理方式一样：重启。

### 步骤 1 · 看屏，确认当前桌面状态

**工具**：`windows-mcp_snapshot`

```
windows-mcp_snapshot(use_vision=True)
```

**看什么**：QQ 主面板是否在前台、有没有弹窗遮挡。

**同时留意 UI 树**：健康状态下 UI 树里会带**元素的屏幕坐标**，直接用这些坐标做 `loc` 最稳。

### 步骤 2 · 把 QQ 切到前台

**首选**：用 Windows API 恢复并置前（`net` 侧脚本即可，比 `app(switch)` 可靠，后者对 QQ 常报 `Application Qq not found`）：

```python
import win32gui, win32con
h = <QQ 主窗口 hwnd>   # 用 EnumWindows 按进程号找，class=Chrome_WidgetWin_1 title="QQ"
win32gui.ShowWindow(h, win32con.SW_RESTORE)
win32gui.SetForegroundWindow(h)
```

**若 QQ 未启动**：

```powershell
Start-Process "<QQ_EXE_PATH>"
Start-Sleep -Seconds 10
```

再用 `windows-mcp_snapshot(use_vision=True)` 确认已登录。

### 步骤 3 · 在搜索框里按 QQ 号搜会话

**工具**：`windows-mcp_type`（**坐标法**）

```
# 搜索框在 UI 树里通常显示为 编辑 "搜索"，取其坐标
windows-mcp_type(loc=[519,137], text="<TARGET_QQ>")
windows-mcp_wait(duration=1)
windows-mcp_snapshot(use_vision=True)
```

**搜索结果**会出现在 UI 树里，形如 `选项 "<PEER_NAME> (<TARGET_QQ>) 来自: 我的好友"`，记下它的坐标。

> ⚠️ **不要用** `click(label="<PEER_NAME>")`：`windows-mcp` 的 `label` 参数要求**数字 id**（不是元素文本），传文本会直接报 `int_parsing` 错误。**统一用坐标 `loc=[x,y]`。**

### 步骤 4 · 打开目标会话

```
windows-mcp_click(loc=[<搜索结果项的坐标>], clicks=1)
windows-mcp_snapshot(use_vision=True)   # 确认右侧聊天区已切到目标会话
```

### 步骤 5 · 定位会话里的文件气泡

**工具**：`windows-mcp_snapshot` + 需要时 `windows-mcp_scroll`

聊天记录可能很长，先滚到目标文件的位置（文件气泡通常是「文件名 + 大小 + 图标」）：

```
windows-mcp_scroll(direction="up", amount=10)
windows-mcp_snapshot(use_vision=True)
```

**精确定位**：用 `System.Drawing` 裁剪文件卡片附近区域再读图，可毫米级确认卡片坐标（比整屏估算准，本 SOP 实战即用此法）：

```powershell
Add-Type -AssemblyName System.Drawing
$bmp=New-Object System.Drawing.Bitmap 520,200
$g=[System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(1420,780,0,0,$bmp.Size)   # 裁剪起点
$bmp.Save('<WORKSPACE>\_dbg_srtcard.png')
```

### 步骤 6 · 右键文件 → 另存为

```
windows-mcp_click(loc=[<文件卡片坐标>], button="right", clicks=1)
windows-mcp_wait(duration=1)
windows-mcp_snapshot(use_vision=True)      # 确认右键菜单弹出
```

菜单里点「另存为」（本次实测菜单项：转发 / 收藏 / 多选 / 引用 / **另存为** / 保存 / 打开 / 删除）：

```
windows-mcp_click(loc=[<另存为 坐标>], clicks=1)
windows-mcp_wait(duration=2)
windows-mcp_snapshot(use_vision=True)      # 确认弹出的是「另存为」对话框
```

**⚠️ 坑**：右键菜单里「另存为」和浏览器/Edge 的菜单项挨得近，先 snapshot 看清菜单来源再点。

### 步骤 7 · 在「另存为」对话框里填路径并保存

**推荐做法：把完整绝对路径放进剪贴板，再粘贴进"文件名"框**（比一层层点目录快且稳，中文/空格不会丢）：

```
windows-mcp_clipboard(mode="set", text="<WORKSPACE>\示例字幕.srt")
windows-mcp_click(loc=[<文件名框坐标>], clicks=1)
windows-mcp_shortcut(shortcut="ctrl+a")
windows-mcp_shortcut(shortcut="ctrl+v")
windows-mcp_shortcut(shortcut="enter")
windows-mcp_wait(duration=2)
```

**⚠️ 注意**
- 对话框默认停在"上次保存目录"（不是你要的位置），务必用整段绝对路径覆盖
- 若弹出「文件已存在，是否覆盖」，先确认不是误覆盖旧文件

---

## 三、验证（不可跳过）

### 1. 确认文件真的落盘

```powershell
Get-Item '<WORKSPACE>\示例字幕.srt' | Select-Object Name, Length, LastWriteTime
```

### 2. 与消息里记录的字节数对一下

**消息 protobuf field 45405 = 文件字节数**（见 1.3）。落盘文件的 `Length` 应与之一致。

**实战基准值**

| 文件 | 字节数 | QQ 显示 |
|---|---|---|
| 示例文档.pdf | 18,138,636 | 17.3 MB |
| 示例字幕.srt | **103,281** | 100.86 KB |

### 3. 确认文件能打开

按用途验证：文本类（srt/md/txt）直接读；PDF 提取文本；扫描件走 OCR。

**srt 转纯文本参考**（去序号+时间码）：

```python
data = open('示例字幕.srt', encoding='utf-8').read().splitlines()
texts, i = [], 0
while i < len(data):
    if data[i].strip().isdigit():
        i += 1
        if i < len(data) and '-->' in data[i]:
            i += 1
            while i < len(data) and data[i].strip():
                texts.append(data[i].strip()); i += 1
        continue
    i += 1
open('示例字幕_纯文本.txt','w',encoding='utf-8').write('\n'.join(texts))
```

---

## 四、本次实测坐标链路（参考，坐标随机型/分辨率变化）

屏幕 2560×1440（100% 缩放），QQ 主面板约 (301,56)-(1835,1135)：

| 环节 | 坐标 |
|---|---|
| QQ 搜索框 | (519, 137) |
| 搜索"<TARGET_QQ>"后结果项 | (570, 251) |
| 会话内「示例字幕.srt」卡片 | (1465,808)-(1765,915) |
| 卡片右键点 | (1560, 870) |
| 右键菜单「另存为」 | (1610, 985) |
| 对话框「文件名」框 | (1559, 918) |

> **注意**：截图附件会被缩小（`Screenshot Coordinate Scale: 1.333333`），附件图像素 × 1.3333 = 传给 click/type 的屏幕坐标。**以 UI 树给出的坐标为准最稳。**

---

## 五、降级方案（windows-mcp 不可用时）

| 情况 | 替代做法 |
|---|---|
| **GUI 自动化完全不可用** | **转用户手动操作**：给出明确步骤（打开 QQ → 找到会话 → 右键文件 → 另存为 → 存到指定路径），由用户自己完成 |
| **只想验证文件在不在** | `windows-mcp_filesystem(mode="search", pattern="*.srt")` 或 PowerShell `Get-ChildItem -Recurse` |
| **截图确认** | `windows-mcp_screenshot`（比 snapshot 轻，只出图不出 UI 树） |
| **不依赖 GUI 直接下载** | **已验证不可行**：文件消息不含下载 URL/rkey；即使从 QQ 进程内存扫到 rkey，配合消息里的 `D6EA...` 串请求 `multimedia.nt.qq.com.cn/download` 也返回 `invalid fileid`。图片消息可走 CDN，文件消息不行。 |

**降级必须留痕**：在 findings 里记录「工具名 + 报错 + 替代路径」。

---

## 六、已知坑清单（实战沉淀）

| # | 坑 | 现象 | 对策 |
|---|---|---|---|
| 1 | **QQ 主面板"僵尸"** | 列表陈旧 + 点击/输入全无响应 + UI 树为空 | **重启 QQ 进程**，再重新定位 |
| 2 | **`label` 参数报错** | `click(label="<PEER_NAME>")` 报 `int_parsing` | `label` 只接受数字 id；**统一改用坐标 `loc=[x,y]`** |
| 3 | **右键误触 Edge 菜单** | 弹出的是浏览器菜单而非 QQ 菜单 | 先 snapshot 确认菜单来源；点「另存为」前再看一次 |
| 4 | **路径输入部分丢失** | 中文/空格被截断 | **整段绝对路径粘贴**（剪贴板），不要分步敲 |
| 5 | **另存为默认目录不对** | 直接点保存会落到"上次目录" | 用完整路径覆盖"文件名"框 |
| 6 | **等待不足** | 点了但下一步 snapshot 还没更新 | 每个关键动作后 `wait(1~2)` 再 snapshot |
| 7 | **坐标估算偏差** | 点偏到隔壁气泡 | 用 `System.Drawing` 裁剪局部区域读图核准坐标 |
| 8 | **文件尚未接收完** | 气泡显示传输中，右键无「另存为」 | 等传输完成再操作 |
| 9 | **多显示器** | snapshot 只抓主屏 | `snapshot(display=[0,1])` 指定 |

---

## 七、安全检查清单

- [ ] **只读操作**：本流程不修改 QQ 内任何内容（不转发、不删除消息）
- [ ] **重启告知**：重启 QQ 会短暂关闭客户端（自动重登），必要时先告知用户
- [ ] **不覆盖旧文件**：另存为时确认目标路径没有同名旧文件，除非明确要覆盖
- [ ] **落盘位置合规**：存进工作区对应目录，不落系统临时目录
- [ ] **文件来源登记**：非公开渠道来源的，在文件名或台账里标注来源性质
- [ ] **大文件校验**：超过 100 MB 的，落盘后核对字节数，防传输中断导致的残缺

---

## 八、工具速查

| 环节 | 工具 | 关键参数 |
|---|---|---|
| 看屏 | `windows-mcp_snapshot` | `use_vision=True`（UI 树含坐标） |
| 轻量截图 | `windows-mcp_screenshot` | `width_reference_line` |
| 点击 | `windows-mcp_click` | `loc=[x,y]`, `button="right"`, `clicks=`（**label 只收数字 id**） |
| 输入 | `windows-mcp_type` | `loc=[x,y]`, `text=` |
| 快捷键 | `windows-mcp_shortcut` | `shortcut="ctrl+v"` |
| 滚屏 | `windows-mcp_scroll` | `direction=`, `amount=` |
| 剪贴板 | `windows-mcp_clipboard` | `mode="set"/"get"`, `text=` |
| 等待 | `windows-mcp_wait` | `duration=`（秒） |
| 系统命令 | `windows-mcp_powershell` | `command=`（**非受限令牌，输入注入才有效**） |
| 本地截图 | PowerShell `System.Drawing` | `CopyFromScreen` |
| 窗口置前 | Python `win32gui` | `ShowWindow` + `SetForegroundWindow` |

---

## 九、待补充

1. QQ 版本对右键菜单项名称的影响（不同版本可能叫「保存到」）
2. 多文件批量导出的最优做法（逐个另存 vs 拖拽到文件夹）
3. QQ 文件默认缓存路径（若能从缓存直接拷，可跳过 GUI）
4. 无 GUI（纯命令行）通道：目前判断为不存在（文件消息不携带可下载 URL）

---

*v1.0 · 2026-09-27 · 基准案例：示例文档 PDF*
*v1.1 · 案例日期二 · 基准案例：示例字幕.srt；新增「僵尸面板→重启」「label 限制」「坐标链路」「字节数核对」，明确 CDN 直连不可行*
