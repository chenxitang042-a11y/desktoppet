"""天气。移植自 Mac 版 WeatherManager,用免费的 wttr.in。

按 IP 自动判断城市,不要密钥、不要定位权限。这套跨平台,Windows 原样能用。
拿不到数据就静默失败,不影响其它功能。后台线程拉取,不卡界面。
"""
import threading
import urllib.request

from settings import settings
from failure_log import failure_log


def _classify(text):
    t = (text or "").lower()
    if any(k in t for k in ("snow", "sleet", "blizzard")):
        return "snow"
    if any(k in t for k in ("rain", "drizzle", "shower", "thunder")):
        return "rain"
    if any(k in t for k in ("clear", "sunny")):
        return "clear"
    return "unknown"


class WeatherMonitor:
    def __init__(self):
        self.current = "unknown"
        self._on_change = None

    def set_callback(self, cb):
        self._on_change = cb

    def fetch_async(self):
        """后台拉一次天气。"""
        if not settings.get("weather_enabled"):
            return
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            req = urllib.request.Request(
                "https://wttr.in/?format=%C",
                headers={"User-Agent": "curl/8"},   # wttr.in 对 UA 敏感
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("utf-8", "ignore").strip()
            failure_log.clear("天气")
            kind = _classify(text)
            if kind != self.current:
                self.current = kind
                if self._on_change:
                    self._on_change(kind)
        except Exception as e:
            failure_log.record("天气", f"获取失败:{e}")


weather = WeatherMonitor()
