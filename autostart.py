"""开机自动启动(Windows)。写注册表 Run 键。

非 Windows 或打包外运行时静默跳过。
"""
import sys

_APP_NAME = "DesktopPet"


def _exe_path():
    # 打包成 exe 后 sys.executable 就是 exe 本身
    if getattr(sys, "frozen", False):
        return sys.executable
    return None


def set_enabled(enabled):
    if not sys.platform.startswith("win"):
        return
    exe = _exe_path()
    if not exe:
        return  # 没打包(开发运行)时不处理
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass
