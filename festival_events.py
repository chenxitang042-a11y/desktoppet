"""节日彩蛋 + 稀有事件。移植自 Mac 版 FestivalManager / RareEvents。

节日:按日期在特定节日说句话,每个节日每年只触发一次。
稀有事件:极低概率的特别时刻,每天最多几次,打破定时器的机械感。
触发记录存本机。
"""
import json
import random
from datetime import datetime, date

from paths import support_path
from settings import settings


class _Flags:
    """记录"某个一次性事件今年/今天有没有触发过"。"""
    def __init__(self):
        self._path = support_path("events.json")
        self._data = {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def check_and_set(self, key):
        if self._data.get(key):
            return False
        self._data[key] = True
        self._save()
        return True

    def get_int(self, key, default=0):
        return int(self._data.get(key, default))

    def set_int(self, key, val):
        self._data[key] = val
        self._save()

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


_flags = _Flags()

# 固定公历节日:(月, 日) -> (标识, 台词)
_FESTIVALS = {
    (1, 1):   ("newyear",   "新的一年了。"),
    (2, 14):  ("valentine", "情人节快乐。"),
    (12, 24): ("xmaseve",   "平安夜快乐。"),
    (12, 25): ("christmas", "圣诞快乐。"),
}


def festival_greeting_today():
    """今天有节日就返回该说的话(每年一次),否则 None。"""
    now = datetime.now()
    y, m, d = now.year, now.month, now.day

    # 生日(设置里填 MM-DD)
    bday = (settings.get("birthday") or "").strip()
    if bday:
        parts = bday.replace("/", "-").split("-")
        try:
            if len(parts) == 2 and int(parts[0]) == m and int(parts[1]) == d:
                if _flags.check_and_set(f"festival_birthday_{y}"):
                    return "生日快乐。"
        except ValueError:
            pass

    hit = _FESTIVALS.get((m, d))
    if hit:
        key, text = hit
        if _flags.check_and_set(f"festival_{key}_{y}"):
            return text
    return None


# 稀有事件台词池(不依赖 AI 的兜底;配了 AI 会优先用 role_lines 的 rare 场景)
_RARE_LINES = [
    "刚才走神了一下。",
    "有时候会想,你看不见我的时候我在做什么。",
    "窗外的光变了。",
    "忽然想起一件事,又忘了。",
    "就这样待着,也挺好。",
]

_MAX_RARE_PER_DAY = 3


def rare_event_line(probability=0.02):
    """低概率返回一句稀有台词,每天有上限。否则 None。"""
    today = date.today().isoformat()
    day_key = f"rare_day_{today}"
    count = _flags.get_int(day_key, 0)
    if count >= _MAX_RARE_PER_DAY:
        return None
    if random.random() > probability:
        return None
    _flags.set_int(day_key, count + 1)
    return random.choice(_RARE_LINES)
