<#
.SYNOPSIS
    把屏幕上的一块区域裁剪成图片，用于在整屏截图上难以确定文件卡片坐标时做毫米级核准。

.DESCRIPTION
    依据 System.Drawing 的 Graphics.CopyFromScreen 实现：按屏幕绝对坐标抓取指定矩形，
    另存为 PNG。

    坐标来自 windows-mcp snapshot 返回的屏幕坐标，直接换算即可；注意附件截图可能被
    按比例缩放，务必以 UI 树给出的坐标为准。

    Windows PowerShell 5.1 以 ANSI 读取无 BOM 的 UTF-8 脚本，本文件的中文帮助与提示
    可能显示为乱码（不影响功能）。推荐用 PowerShell 7+（pwsh）运行，它默认按 UTF-8 解析。

.EXAMPLE
    .\crop_screenshot.ps1 -X 1420 -Y 780 -Width 520 -Height 200
    抓取以 (1420,780) 为左上角的 520x200 区域，保存到系统临时目录。

.EXAMPLE
    .\crop_screenshot.ps1 -X 1420 -Y 780 -Width 520 -Height 200 -OutPath 'C:\Path\To\crop.png'
    指定输出路径。示例路径，请替换为本机实际位置。
#>
[CmdletBinding()]
param(
    # 裁剪区域左上角的屏幕 X 坐标。
    [ValidateRange(0, 100000)]
    [int]$X = 0,

    # 裁剪区域左上角的屏幕 Y 坐标。
    [ValidateRange(0, 100000)]
    [int]$Y = 0,

    # 裁剪宽度（像素）。
    [ValidateRange(1, 100000)]
    [int]$Width = 520,

    # 裁剪高度（像素）。
    [ValidateRange(1, 100000)]
    [int]$Height = 200,

    # 输出 PNG 路径。省略时写入系统临时目录，文件名带时间戳。
    [string]$OutPath
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

if (-not $OutPath) {
    $OutPath = Join-Path ([System.IO.Path]::GetTempPath()) ('qq_crop_{0}.png' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
}

$outDir = Split-Path -Parent $OutPath
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

$bitmap = $null
$graphics = $null
try {
    $bitmap = New-Object System.Drawing.Bitmap($Width, $Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($X, $Y, 0, 0, $bitmap.Size)
    $bitmap.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host ('[done ] 已保存 {0}x{1}，裁剪起点 ({2},{3}) -> {4}' -f $Width, $Height, $X, $Y, $OutPath)
}
finally {
    if ($graphics) { $graphics.Dispose() }
    if ($bitmap) { $bitmap.Dispose() }
}
