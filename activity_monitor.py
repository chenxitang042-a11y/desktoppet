"""看你在用什么软件。移植自 Mac 版 AppMonitor 的归类思路。

Windows 上用 ctypes 读"当前最前面那个窗口"属于哪个程序,按名字归类:
听歌 / 打字写东西 / 浏览网页看文档 / 其它。

只在 Windows 上真正工作;其它系统(比如打包机之外)自动空转,不报错。
不上传任何数据,只在本机读进程名。
"""
import sys

IS_WINDOWS = sys.platform.startswith("win")

# 归类关键词(和 Mac 版基本一致,补了些 Windows 常见软件)
_CODE = ["code", "vscode", "cursor", "pycharm", "idea", "intellij", "webstorm",
         "goland", "clion", "android studio", "sublime", "devenv", "rider",
         "windowsterminal", "cmd", "powershell", "wt", "notepad++", "zed"]
_MUSIC = ["spotify", "cloudmusic", "netease", "qqmusic", "kugou", "kuwo",
          "applemusic", "foobar", "aimp", "musicbee"]
_VIDEO = ["vlc", "potplayer", "mpv", "quicktime", "bilibili", "iqiyi",
          "youku", "tencentvideo", "kmplayer"]
_READER = ["acrobat", "sumatra", "foxit", "pdf", "calibre", "zotero",
           "wps", "onenote", "kindle", "neat reader"]
_DESIGN = ["figma", "photoshop", "illustrator", "affinity", "blender",
           "pixelmator", "coreldraw"]
_CHAT = ["wechat", "weixin", "qq", "slack", "discord", "telegram", "lark",
         "feishu", "dingtalk", "teams", "zoom"]
_BROWSER = ["chrome", "firefox", "msedge", "edge", "opera", "brave",
            "vivaldi", "360se", "sogou", "qqbrowser", "safari"]
_WRITE = ["winword", "word", "notion", "obsidian", "typora", "notepad",
          "wordpad", "ulysses", "logseq", "scrivener"]


def _foreground_process_name():
    """返回当前最前窗口所属程序的可执行文件名(小写),失败返回空串。"""
    if not IS_WINDOWS:
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            # QueryFullProcessImageNameW
            ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            if not ok:
                return ""
            path = buf.value
            name = path.rsplit("\\", 1)[-1].lower()
            return name
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return ""


def current_activity():
    """返回当前活动类别:music / writing / browsing / other。"""
    name = _foreground_process_name()
    if not name:
        return "other"

    def has(keys):
        return any(k in name for k in keys)

    if has(_MUSIC):
        return "music"
    if has(_CODE) or has(_WRITE):
        return "writing"
    if has(_BROWSER) or has(_READER) or has(_VIDEO) or has(_CHAT):
        return "browsing"
    if has(_DESIGN):
        return "writing"      # 设计也归为"专注做东西",用思考姿势
    return "other"


# 活动类别 -> 角色姿势(对应 animation.py 里的状态)
ACTIVITY_STATE = {
    "music":    "headphones",   # 戴耳机
    "writing":  "think",        # 托腮思考,陪你写
    "browsing": "read",         # 看书姿势,陪你看
    "other":    "idle",
}

# 活动类别 -> 场景台词标识(由 AI 按人设生成)
ACTIVITY_SCENE = {
    "music":    "activity_music",
    "writing":  "activity_writing",
    "browsing": "activity_browsing",
}
