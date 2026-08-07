"""读电量。移植自 Mac 版 BatteryMonitor 的思路。

Windows 用 kernel32.GetSystemPowerStatus 读电量百分比和是否在充电。
低电量(<20% 且没插电)触发一次提醒。
台式机/读取失败时返回 None,不触发。
"""
import sys
import ctypes

IS_WINDOWS = sys.platform.startswith("win")


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),        # 0 断电 / 1 插电 / 255 未知
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),   # 0-100 / 255 未知
        ("SystemStatusFlag", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def read_battery():
    """返回 (百分比, 是否在充电);读不到返回 (None, None)。"""
    if not IS_WINDOWS:
        return None, None
    try:
        status = _SystemPowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None, None
        pct = status.BatteryLifePercent
        ac = status.ACLineStatus
        if pct == 255:            # 没有电池(台式机)
            return None, None
        charging = (ac == 1)
        return int(pct), charging
    except Exception:
        return None, None


class BatteryWatcher:
    """跟踪电量,低电量时回调一次(回充电后重置)。"""

    def __init__(self, low_threshold=20):
        self._low = low_threshold
        self._warned = False

    def check(self):
        """返回 True 表示"现在该提醒低电量了"。"""
        pct, charging = read_battery()
        if pct is None:
            return False
        if charging or pct > self._low:
            self._warned = False      # 充上电或电量回升,重置
            return False
        if not self._warned:
            self._warned = True
            return True
        return False
