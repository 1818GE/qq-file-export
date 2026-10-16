<#
.SYNOPSIS
    重启 QQ 客户端进程，用于修复"僵尸面板"（会话列表陈旧 + 点击/输入无响应 + UI 树为空）。

.DESCRIPTION
    停止所有匹配的 QQ 进程，等待 -WaitSeconds 秒后重新拉起。
    QQ 记住登录态，重启后会自动登录，无需重新输入密码。

    注意：本脚本会短暂关闭本机 QQ 客户端。
    执行前请先告知用户；若检测到有文件正在传输，等接收完成再操作，否则可能中断传输。

    Windows PowerShell 5.1 以 ANSI 读取无 BOM 的 UTF-8 脚本，本文件的中文帮助与提示
    可能显示为乱码（不影响功能）。推荐用 PowerShell 7+（pwsh）运行，它默认按 UTF-8 解析。

.EXAMPLE
    .\restart_qq.ps1
    以运行中进程自身的可执行文件路径重启 QQ，等待 4 秒（默认行为）。

.EXAMPLE
    .\restart_qq.ps1 -ExePath 'C:\Path\To\QQ.exe'
    QQ 尚未运行时显式指定可执行文件。示例路径，请替换为本机实际位置。

.EXAMPLE
    .\restart_qq.ps1 -WaitSeconds 10
    改用 10 秒的停止-启动间隔。
#>
[CmdletBinding()]
param(
    # QQ 可执行文件路径。省略时取运行中进程自身的 Path；
    # QQ 未运行且未提供本参数时报错。
    [string]$ExePath,

    # 停止与启动之间的等待秒数。
    [ValidateRange(0, 600)]
    [int]$WaitSeconds = 4,

    # QQ 主进程名。
    [string]$ProcessName = 'QQ',

    # 只启动不停止，用于 QQ 未运行时的冷启动。
    [switch]$SkipStop
)

$ErrorActionPreference = 'Stop'

function Resolve-QqExecutable {
    param(
        [string]$ExplicitPath,
        [string]$Name
    )

    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "指定的 QQ 可执行文件不存在：$ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).ProviderPath
    }

    $running = @(Get-Process -Name $Name -ErrorAction SilentlyContinue |
        Where-Object { $_.Path } |
        Select-Object -First 1)
    if ($running.Count -gt 0) {
        return $running[0].Path
    }

    # 路径示例见本脚本头部 .EXAMPLE，本处不写死任何机器路径。
    throw "未找到运行中的 '$Name' 进程，且未提供 -ExePath。请用 -ExePath 显式指定 QQ.exe（示例见脚本头部 .EXAMPLE）"
}

$exe = Resolve-QqExecutable -ExplicitPath $ExePath -Name $ProcessName

if ($SkipStop) {
    Write-Host '[skip ] -SkipStop：未停止任何进程。'
}
else {
    $targets = @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)
    if ($targets.Count -gt 0) {
        Write-Host "[stop ] 正在停止 $($targets.Count) 个 '$ProcessName' 进程 ..."
        $targets | Stop-Process -Force
    }
    else {
        Write-Host "[stop ] 没有运行中的 '$ProcessName' 进程，跳过停止。"
    }
}

Write-Host "[wait ] 等待 $WaitSeconds 秒 ..."
Start-Sleep -Seconds $WaitSeconds

Write-Host "[start] 启动 $exe ..."
Start-Process -FilePath $exe

Write-Host '[done ] QQ 已重新拉起。等主窗口就绪后再执行一次 snapshot，确认 UI 树可读、会话列表已刷新。'
