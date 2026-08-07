"""锁屏 / 解锁检测。对应 Mac 版 SystemMonitor 的锁屏部分。

Windows 没有像 Mac 那样现成的通知,这里用一个稳妥的办法:
尝试打开"当前输入桌面",锁屏时会失败 —— 以此判断是否处于锁定状态。
从"锁定"变回"未锁定"时,回调一次(桌宠可以打个招呼)。
非 Windows 永远返回未锁定。
"""
import sys
import ctypes

IS_WINDOWS = sys.platform.startswith("win")


def is_locked():
    """锁屏返回 True。读不到时按未锁定处理。"""
    if not IS_WINDOWS:
        return False
    try:
        # DESKTOP_SWITCHDESKTOP = 0x0100
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
        if not hdesk:
            return True   # 打不开输入桌面 = 锁屏中
        ctypes.windll.user32.CloseDesktop(hdesk)
        return False
    except Exception:
        return False


class LockWatcher:
    """跟踪锁屏状态变化。unlocked() 在刚解锁的那一刻返回 True。"""

    def __init__(self):
        self._was_locked = False

    def poll(self):
        """返回 (刚锁屏, 刚解锁)。"""
        locked = is_locked()
        just_locked = locked and not self._was_locked
        just_unlocked = (not locked) and self._was_locked
        self._was_locked = locked
        return just_locked, just_unlocked
