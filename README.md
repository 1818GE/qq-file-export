# qq-file-export

把别人通过 QQ 发来的文件（PDF / 压缩包 / 文档 / 字幕 / 图片）从本机 QQ 客户端导出到本地工作区。QQ 的文件消息里不含可用的下载地址和 rkey，CDN 直连和纯命令行通道都已验证走不通，唯一可行的是驱动 QQ 客户端的 GUI 把文件「另存为」下来；这个包把那条路径固化成可复用的七步 SOP、实战踩坑清单、三个参数化的 PowerShell 脚本，以及一个只依赖标准库的环境自检脚本。

## 快速开始

1. **安装**：把本目录复制到 `~/.hanako/skills/qq-file-export/`，新开一个会话。详见 [setup-guide.md](setup-guide.md)。
2. **确认依赖**：windows-mcp 连接器需为 `running`，本机 QQ 客户端需已登录。
3. **自检**：

   ```powershell
   python check_environment.py
   ```

   打印就绪清单，全部就绪退出码 `0`，任一项缺失退出码 `1`。
4. **触发**：用下面的任意一句触发语说出需求，Agent 会按 [references/sop.md](references/sop.md) 走完整流程。

## 触发语

- 我在 QQ 发了个文件
- 从 QQ 下载这个文件
- 把 QQ 收到的文件拿下来
- QQ 文件另存为
- 导出 QQ 文件
- 读取 QQ 发来的文件
- QQ 里那个 srt / pdf / 压缩包

以下情况**不应**触发本技能：QQ 好友申请管理、撤回消息、导出聊天记录成表格、QQ 表情包保存。

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/restart_qq.ps1` | 重启 QQ 进程，修复「僵尸面板」（列表陈旧 + 点击失灵 + UI 树为空）。默认停止后等 4 秒再启动。 |
| `scripts/verify_file_bytes.ps1` | 打印文件 Length 与 SHA256，与 QQ 消息记录里的字节数对账。可传 `-ExpectedBytes` 直接判定并返回退出码。 |
| `scripts/crop_screenshot.ps1` | 用 System.Drawing 裁剪屏幕区域，整屏截图难以确定文件卡片坐标时做毫米级核准。 |

三个脚本都带 `param` 块，不写死任何机器路径。

## 工作流程七步

1. 判断 QQ 主面板是否为「僵尸面板」，是则重启进程
2. 看屏（snapshot），记住 UI 树里的屏幕坐标
3. 把 QQ 切到前台
4. 搜索对方 QQ 号
5. 打开目标会话
6. 定位文件气泡，必要时裁剪局部区域核准坐标
7. 右键 → 另存为 → 剪贴板粘贴完整路径 → 保存

落盘后必须核对字节数：QQ 消息 protobuf `40800` 里 field `45405` 的 varint 就是发送方的文件字节数。

## 目录结构

```
qq-file-export/
├── SKILL.md                  # 技能入口：触发条件、流程、坑清单
├── README.md                 # 本文件
├── LICENSE                   # MIT
├── setup-guide.md            # 安装、依赖说明、降级路径
├── skill-dependencies.json   # 运行期依赖声明
├── check_environment.py      # 环境自检（仅标准库）
├── references/
│   └── sop.md                # 完整操作 SOP
└── scripts/
    ├── restart_qq.ps1
    ├── verify_file_bytes.ps1
    └── crop_screenshot.ps1
```

## 不成立的通道

写在这里是为了省下后来者重复验证的时间：

- **CDN 直连**：文件消息的 `40800` 不含下载 URL / rkey，只有图片消息内嵌 `multimedia.nt.qq.com.cn/download?...&rkey=...`。
- **纯命令行通道**：目前判断不存在。

## 许可

MIT，见 [LICENSE](LICENSE)。
