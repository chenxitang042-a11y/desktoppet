"""陪伴记录。移植自 Mac 版 CompanionRecord,并扩展了聊天次数统计。

记录:第一次见面时间、相伴天数、累计聊天次数、今天聊了几次。
到里程碑天数(7/30/100…)时提醒一句。
"""
import json
import time
from datetime import date, datetime

from paths import support_path

MILESTONES = [7, 30, 100, 200, 365, 500, 730, 1000]


class CompanionRecord:
    def __init__(self):
        self._path = support_path("companion.json")
        self._data = {
            "first_launch": None,   # 时间戳
            "total_chats": 0,
            "today": "",            # 今天的日期字符串
            "today_chats": 0,
            "milestones_said": [],  # 已经说过的里程碑
        }
        self.load()
        self._ensure_first_launch()

    def _ensure_first_launch(self):
        if not self._data.get("first_launch"):
            self._data["first_launch"] = time.time()
            self.save()

    @property
    def first_launch_date(self):
        return datetime.fromtimestamp(self._data["first_launch"])

    @property
    def days_together(self):
        start = self.first_launch_date.date()
        return (date.today() - start).days

    def note_chat(self):
        """每聊一次调一下。"""
        today = date.today().isoformat()
        if self._data.get("today") != today:
            self._data["today"] = today
            self._data["today_chats"] = 0
        self._data["today_chats"] += 1
        self._data["total_chats"] += 1
        self.save()

    @property
    def total_chats(self):
        return self._data.get("total_chats", 0)

    @property
    def today_chats(self):
        if self._data.get("today") != date.today().isoformat():
            return 0
        return self._data.get("today_chats", 0)

    def milestone_greeting_if_any(self):
        """今天到里程碑了就返回该说的话(每个只触发一次),否则 None。"""
        days = self.days_together
        if days not in MILESTONES:
            return None
        said = self._data.get("milestones_said", [])
        if days in said:
            return None
        said.append(days)
        self._data["milestones_said"] = said
        self.save()
        return f"我们已经认识 {days} 天了。"

    def summary_lines(self):
        d = self.first_launch_date
        return [
            f"第一次见面:{d.year}年{d.month}月{d.day}日",
            f"已经陪伴:{self.days_together} 天",
            f"累计聊天:{self.total_chats} 次",
            f"今天聊了:{self.today_chats} 次",
        ]

    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self._data.update(saved)
        except Exception:
            pass


companion = CompanionRecord()
