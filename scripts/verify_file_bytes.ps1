<#
.SYNOPSIS
    打印导出文件的字节数与 SHA256，用于和 QQ 消息记录里的字节数对账。

.DESCRIPTION
    另存为之后必须做的一步：文件消息 protobuf（field 40800）里 field 45405 的 varint
    就是发送方的文件字节数，与本脚本输出的 Length 比对即可判断落盘是否完整。
    SHA256 用于跨机器/跨来源核对同一文件。

    退出码：全部对账通过 0；任一文件缺失或字节数不符 1。

    Windows PowerShell 5.1 以 ANSI 读取无 BOM 的 UTF-8 脚本，本文件的中文帮助与提示
    可能显示为乱码（不影响功能）。推荐用 PowerShell 7+（pwsh）运行，它默认按 UTF-8 解析。

.EXAMPLE
    .\verify_file_bytes.ps1 -Path 'C:\Path\To\subtitle.srt'
    只打印 Length 与 SHA256。示例路径，请替换为本机实际位置。

.EXAMPLE
    .\verify_file_bytes.ps1 -Path 'C:\Path\To\subtitle.srt' -ExpectedBytes 103281
    同时与 QQ 消息记录里的字节数对账，不符时退出码为 1。
#>
[CmdletBinding()]
param(
    # 待校验的文件路径，可传多个。
    [Parameter(Mandatory = $true, Position = 0, ValueFromPipeline = $true)]
    [string[]]$Path,

    # 期望字节数，取自 QQ 消息 protobuf field 45405。默认 -1 表示只输出不做对账。
    [long]$ExpectedBytes = -1
)

$ErrorActionPreference = 'Stop'
$failed = $false

foreach ($target in $Path) {
    Write-Host "=== $target ==="

    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        Write-Host '  [MISS ] 文件不存在。'
        $failed = $true
        continue
    }

    $item = Get-Item -LiteralPath $target
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash

    Write-Host ('  Length  : {0}' -f $item.Length)
    Write-Host ('  SHA256  : {0}' -f $hash)
    Write-Host ('  Modified: {0}' -f $item.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))

    if ($ExpectedBytes -ge 0) {
        if ($item.Length -eq $ExpectedBytes) {
            Write-Host ('  Reconcile: OK，与消息记录一致（{0} 字节）' -f $ExpectedBytes)
        }
        else {
            $delta = $item.Length - $ExpectedBytes
            Write-Host ('  Reconcile: MISMATCH，期望 {0}，实际 {1}，相差 {2} 字节。文件可能未传完。' -f $ExpectedBytes, $item.Length, $delta)
            $failed = $true
        }
    }
}

if ($failed) {
    Write-Host '结论：校验未通过。'
    exit 1
}

Write-Host '结论：校验通过。'
exit 0
