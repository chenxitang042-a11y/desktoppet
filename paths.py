"""路径与数据目录。

对应 Mac 版的 AssetLoader.supportDirectory。
Windows 上把用户数据放在 %APPDATA%\\DesktopPet\\,
和程序本体(exe)分开 —— 卸载删 exe 不会连着删掉聊天记录和设定。
"""
import os
import sys


def resource_dir() -> str:
    """素材(PetImages 等)所在目录。

    PyInstaller 打包成单文件 exe 后,运行时会把资源解压到临时目录,
    路径存在 sys._MEIPASS。没打包时就用脚本所在目录。
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def images_dir() -> str:
    return os.path.join(resource_dir(), "PetImages")


def support_dir() -> str:
    """用户数据目录。放聊天记录、角色设定、配置。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "DesktopPet")
    os.makedirs(d, exist_ok=True)
    return d


def support_path(name: str) -> str:
    return os.path.join(support_dir(), name)
