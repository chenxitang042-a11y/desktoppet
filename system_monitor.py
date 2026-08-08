"""真实空闲检测。移植自 Mac 版 SystemMonitor 的空闲部分。

Windows 用 GetLastInputInfo 读"全系统距上次键鼠输入过了多久"。
不是"没戳桌宠",而是你真的离开了。人离开一阵 -> 桌宠去睡觉。
非 Windows 返回 0(视为一直活跃)。
"""
import sys
import ctypes

IS_WINDOWS = sys.platform.startswith("win")


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


def idle_seconds():
    """返回距上次键鼠输入的秒数;读不到返回 0。"""
    if not IS_WINDOWS:
        return 0
    try:
        info = _LastInputInfo()
        info.cbSize = ctypes.sizeof(_LastInputInfo)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0, millis / 1000.0)
    except Exception:
        return 0


def foreground_is_fullscreen():
    """当前最前窗口是否占满整个屏幕(看视频/演示/游戏)。读不到返回 False。"""
    if not IS_WINDOWS:
        return False
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        # 桌面/任务栏不算
        shell = user32.GetShellWindow()
        if hwnd == shell:
            return False
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        sh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        return w >= sw and h >= sh
    except Exception:
        return False
