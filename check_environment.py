#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qq-file-export 环境自检（只使用 Python 标准库）。

导出链路真正依赖的外部条件只有两类：

1. windows-mcp 连接器
   - 配置已启用：~/.hanako/agents/<agent>/config.yaml 中 extensions.connector.windows-mcp.enabled
   - 服务进程在跑：系统里存在 windows-mcp.exe 进程
2. 本机 QQ 客户端
   - QQ.exe 进程存在
   - 至少有一个可见主窗口（窗口标题非空），否则面板多半是"僵尸面板"
   - QQ 可执行文件路径可解析，restart_qq.ps1 需要它

退出码：全部就绪 0；任一项缺失 1。
用法：python check_environment.py
"""

import ctypes
import glob
import io
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
import unicodedata
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"
HANA_HOME = os.path.join(os.path.expanduser("~"), ".hanako")

CONNECTOR_BLOCK = re.compile(r"^(\s*)connector\s*:\s*$")
CONNECTOR_ENTRY = re.compile(r"^\s*windows-mcp\s*:\s*$")
ENABLED_VALUE = re.compile(r"^\s*enabled\s*:\s*([A-Za-z]+)\s*$")


def _use_utf8_stdout():
    """让输出稳定为 UTF-8，避免在非 UTF-8 控制台上抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _indent(line):
    return len(line) - len(line.lstrip())


def _read_lines(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read().splitlines()


def hana_home():
    """Hana 主目录。当前部署没有对应的环境变量，固定为用户目录下的 .hanako。"""
    return HANA_HOME


# --------------------------------------------------------------------------
# 检查项 1：windows-mcp 连接器配置
# --------------------------------------------------------------------------
def agents_with_connector_enabled():
    """返回已启用 windows-mcp 连接器的 agent 名列表。

    只认 extensions.connector 块下的 windows-mcp：同名的 windows-mcp 技能也出现在
    同一个文件里，只按名字 grep 会误判。
    """
    pattern = os.path.join(hana_home(), "agents", "*", "config.y*ml")
    agents = []
    for path in sorted(glob.glob(pattern)):
        try:
            lines = _read_lines(path)
        except OSError:
            continue
        for index, line in enumerate(lines):
            match = CONNECTOR_BLOCK.match(line)
            if not match:
                continue
            base_indent = _indent(line)
            block = []
            for follow in lines[index + 1:]:
                if follow.strip() and _indent(follow) <= base_indent:
                    break
                block.append(follow)
            if _block_enables_windows_mcp(block):
                agents.append(os.path.basename(os.path.dirname(path)))
                break
    return agents


def _block_enables_windows_mcp(block):
    for index, line in enumerate(block):
        if not CONNECTOR_ENTRY.match(line):
            continue
        entry_indent = _indent(line)
        for follow in block[index + 1:]:
            value = ENABLED_VALUE.match(follow)
            if value:
                return value.group(1).lower() == "true"
            if follow.strip() and _indent(follow) <= entry_indent:
                return False
    return False


# --------------------------------------------------------------------------
# 检查项 2：进程表
# --------------------------------------------------------------------------
def tasklist_rows():
    """返回 [(镜像名小写, pid)]；无法枚举时返回 None。"""
    if not IS_WINDOWS:
        return None
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    encoding = locale.getpreferredencoding(False) or "utf-8"
    rows = []
    for line in result.stdout.decode(encoding, "replace").splitlines():
        if not line.strip():
            continue
        fields = line.split('","')
        if len(fields) < 2:
            continue
        name = fields[0].strip('"').lower()
        try:
            pid = int(fields[1])
        except ValueError:
            continue
        rows.append((name, pid))
    return rows


def pids_named(rows, image):
    return sorted(pid for name, pid in rows if name == image)


# --------------------------------------------------------------------------
# 检查项 3：窗口与进程可执行文件路径（ctypes，无需外部依赖）
# --------------------------------------------------------------------------
if IS_WINDOWS:
    _kernel32 = ctypes.windll.kernel32
    _user32 = ctypes.windll.user32

    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL

    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL


def visible_windows():
    """返回 [(hwnd, pid, title)]，只含可见且有标题的顶层窗口。"""
    if not IS_WINDOWS:
        return []
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _collect(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buffer, length + 1)
        found.append((hwnd, pid.value, buffer.value))
        return True

    callback = callback_type(_collect)
    _user32.EnumWindows(callback, 0)
    return found


def process_image_path(pid):
    """返回进程的完整可执行文件路径；失败返回 None。"""
    if not IS_WINDOWS:
        return None
    process_query_limited_information = 0x1000
    handle = _kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        query = getattr(_kernel32, "QueryFullProcessImageNameW", None)
        if query is None:
            return None
        query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        query.restype = wintypes.BOOL
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if query(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return None
    finally:
        _kernel32.CloseHandle(handle)


def first_qq_window(qq_pids):
    """返回第一个属于 QQ 进程的可见窗口标题，找不到返回 None。"""
    if not qq_pids:
        return None
    wanted = set(qq_pids)
    for _hwnd, pid, title in visible_windows():
        if pid in wanted and title:
            return title
    return None


# --------------------------------------------------------------------------
# 检查项 4：PowerShell
# --------------------------------------------------------------------------
def powershell_path():
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def display_width(text):
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


class Checklist(object):
    def __init__(self):
        self.items = []

    def add(self, ok, label, detail):
        self.items.append((bool(ok), label, detail))

    def render(self):
        pad = max(display_width(label) for _ok, label, _detail in self.items)
        lines = []
        for ok, label, detail in self.items:
            marker = "[ OK ]" if ok else "[MISS]"
            gap = " " * (pad - display_width(label))
            suffix = "  ({0})".format(detail) if detail else ""
            lines.append("  {0}  {1}{2}{3}".format(marker, label, gap, suffix))
        return "\n".join(lines)

    @property
    def all_ok(self):
        return all(ok for ok, _label, _detail in self.items)


def main():
    _use_utf8_stdout()

    print("qq-file-export 环境自检")
    print("  平台     : {0} / Python {1}".format(platform.platform(), platform.python_version()))
    print("  Hana 主目录: {0}".format(hana_home()))

    rows = tasklist_rows()
    if rows is None:
        print("  警告：无法读取进程表（tasklist 不可用），进程类检查项按缺失处理。")
        rows = []

    mcp_pids = pids_named(rows, "windows-mcp.exe")
    qq_pids = pids_named(rows, "qq.exe")
    qq_title = first_qq_window(qq_pids)
    qq_exe = process_image_path(qq_pids[0]) if qq_pids else None
    shell = powershell_path()

    checklist = Checklist()
    agents = agents_with_connector_enabled()
    checklist.add(
        agents,
        "windows-mcp 连接器已启用",
        "agents: {0}".format(", ".join(agents)) if agents else "~/.hanako/agents/*/config.yaml 未见 extensions.connector.windows-mcp.enabled: true",
    )
    checklist.add(
        mcp_pids,
        "windows-mcp 服务进程运行中",
        "pid {0}".format(", ".join(str(pid) for pid in mcp_pids)) if mcp_pids else "未找到 windows-mcp.exe",
    )
    checklist.add(
        qq_pids,
        "QQ 客户端进程运行中",
        "{0} 个 QQ.exe".format(len(qq_pids)) if qq_pids else "未找到 QQ.exe，请先启动并登录 QQ",
    )
    checklist.add(
        qq_title,
        "QQ 主窗口可见",
        "标题 {0}".format(qq_title) if qq_title else "所有 QQ 进程窗口标题为空：面板可能是僵尸面板，需重启 QQ",
    )
    checklist.add(
        qq_exe,
        "QQ 可执行文件路径可解析",
        qq_exe or "无法读取进程路径，restart_qq.ps1 将需要 -ExePath 参数",
    )
    checklist.add(
        shell,
        "PowerShell 可用",
        shell or "PATH 中找不到 pwsh / powershell",
    )

    print()
    print(checklist.render())
    print()

    if checklist.all_ok:
        print("结论：环境就绪，可以按 references/sop.md 执行导出流程。")
        return 0
    print("结论：环境未就绪，请先按 setup-guide.md 处理标记为 MISS 的项目。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
