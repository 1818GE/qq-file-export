# qq-file-export 安装与环境准备

本文件覆盖三件事：把技能装进 Hana、确认 windows-mcp 依赖可用、依赖不可用时怎么降级。

---

## 一、安装

### 1. 复制技能目录

把整个 `qq-file-export/` 目录放进 Hana 的技能根目录：

```
~/.hanako/skills/qq-file-export/
```

Windows 上的实际路径形如 `C:\Users\<用户名>\.hanako\skills\qq-file-export\`。

### 2. 确认技能已被识别

技能靠 `SKILL.md` 的 YAML frontmatter 注册，关键字段是 `name` 和 `description`。确认：

- `SKILL.md` 存在且首行是 `---`
- `name: qq-file-export` 与目录名一致

装完建议新开一个会话再触发，让运行时重新扫描技能目录。

### 3. 准备脚本运行环境

`scripts/` 下三个脚本需要 PowerShell：

| 脚本 | 用途 |
|---|---|
| `scripts/restart_qq.ps1` | 重启 QQ 进程，修复"僵尸面板" |
| `scripts/verify_file_bytes.ps1` | 打印文件 Length 与 SHA256，与 QQ 消息记录的字节数对账 |
| `scripts/crop_screenshot.ps1` | 裁剪屏幕区域，用于核准文件卡片坐标 |

优先用 PowerShell 7+（`pwsh`）。Windows 自带的 PowerShell 5.1 也能跑，但它把无 BOM 的 UTF-8 脚本按 ANSI 解析，中文帮助和提示会显示成乱码，**功能不受影响**。

### 4. 跑一次环境自检

```powershell
python check_environment.py
```

逐项打印就绪清单，全部就绪时退出码 `0`，任一项缺失时退出码 `1`。只依赖 Python 标准库，不需要装任何东西。

---

## 二、windows-mcp 依赖说明

### 为什么这个依赖不可省略

QQ 的文件消息（protobuf `40800`）里**不含下载 URL 和 rkey**。只有图片消息才内嵌 `multimedia.nt.qq.com.cn/download?...&rkey=...`。即使从 QQ 进程内存里扫到 rkey，拿消息里的 `D6EA...` 串去请求也会返回 `invalid fileid`。

也就是说这条链路上：

- CDN 直连：**已验证不可行**
- 纯命令行：**已验证不存在**
- GUI 另存为：**唯一可行路径**

所以本技能把 windows-mcp 当作硬依赖，而不是可选加速项。

### 依赖提供的能力

| 工具 | 在本技能里的用途 |
|---|---|
| `snapshot` | 看屏，UI 树里带元素屏幕坐标，是坐标的主要来源 |
| `click` | 左键/右键点击，含 `button="right"` |
| `type` | 在搜索框输入 QQ 号 |
| `scroll` | 长会话里滚到文件气泡 |
| `clipboard` | 粘贴整段绝对路径，避免中文和空格被截断 |
| `shortcut` | `ctrl+a` / `ctrl+v` / `enter` |
| `wait` | 每个关键动作后等 1~2 秒 |
| `screenshot` | 轻量截图，只出图不出 UI 树 |

### 如何启用

连接器状态通过平台的连接器管理入口查询和切换，**不要手工编辑配置文件**：配置有校验、权限检查和缓存刷新，手改容易出现「文件已保存但运行时未生效」。

Hana 里对应的配置位置是 `~/.hanako/agents/<agent>/config.yaml` 的 `extensions.connector.windows-mcp`，启用项形如 `windows-mcp: { enabled: true }`。这一项只作为排查线索列出，供你在管理入口找不到时定位；日常操作走管理入口。

连接器状态可以这样确认：

```
mcp_connectors_status
```

期望 `windows-mcp` 为 `running`。连接器改动通常需要新会话才生效。

### 自检脚本怎么判断它可用

`check_environment.py` 用两个独立信号交叉验证，避免只看配置就误报就绪：

1. **配置信号**：扫描 `~/.hanako/agents/*/config.yaml`，定位 `extensions.connector` 块下的 `windows-mcp.enabled`。注意同名技能也在同一文件里，只按名字 grep 会误判，所以脚本按缩进层级解析块结构。
2. **运行信号**：进程表里存在 `windows-mcp.exe`。

---

## 三、降级路径：windows-mcp 不可用时

**结论先行：降级不等于技能失效，但导出这一步必须由用户手动完成。**

| 情况 | 替代做法 |
|---|---|
| GUI 自动化完全不可用 | **转用户手动操作**。给出明确步骤：打开 QQ → 搜索对方 QQ 号 → 找到文件气泡 → 右键 → 另存为 → 存到指定路径 |
| 只想确认文件在不在 | `Get-ChildItem -Recurse -Filter <文件名>` 或 windows-mcp 的 `filesystem(mode="search")` |
| 只想看屏幕 | 本地 `scripts/crop_screenshot.ps1`，不依赖连接器 |
| 想重启 QQ 恢复面板 | 本地 `scripts/restart_qq.ps1`，不依赖连接器 |
| 想核对文件是否完整 | 本地 `scripts/verify_file_bytes.ps1`，不依赖连接器 |
| 想不靠 GUI 直接下载 | **已验证不可行**，见上一节 |

三条脚本和自检脚本都不依赖连接器，所以即使连接器挂了，你仍然能完成「重启客户端」「核准坐标」「核对字节数」这三件事，只剩下「点右键 → 另存为」需要人来做。

### 降级必须留痕

走降级路径时，在 findings 里记录三件事：

1. 用了哪个工具（或哪个脚本）
2. 具体报错原文
3. 实际走的替代路径

没有留痕的降级，下次排查时等于没发生过。

---

## 四、故障速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 自检报 `MISS windows-mcp 连接器已启用` | 配置里没启用，或配置在别的 agent 下 | 走连接器管理入口启用，确认生效的 agent 与当前会话一致 |
| 自检报 `MISS windows-mcp 服务进程运行中` | 连接器没启动 | 重启 Hana 或让 mcp-keepalive 重连 |
| 自检报 `MISS QQ 主窗口可见` | 窗口标题全空，面板多半已僵 | `.\scripts\restart_qq.ps1`，重启前先告知用户 |
| `restart_qq.ps1` 报「未找到运行中的进程」 | QQ 没在跑 | `-SkipStop` 冷启动，或显式给 `-ExePath 'C:\Path\To\QQ.exe'` |
| 脚本文本里的中文显示成乱码 | Windows PowerShell 5.1 的 ANSI 解析 | 改用 `pwsh` 执行，功能本身不受影响 |
| 截图脚本报找不到 System.Drawing | 运行环境不含该程序集 | 确认在 Windows 上用 PowerShell 5.1 或 7+ 运行 |

---

## 五、卸载

删除技能目录即可，无外部状态需要清理。`check_environment.py` 只读系统和 Hana 配置，不写任何文件。
