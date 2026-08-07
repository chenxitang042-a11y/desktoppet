"""桌宠的提醒。

Windows 没有能可靠读取的系统日历接口,所以做成桌宠自己的提醒:
你告诉它"几点提醒我做什么",到点它用符合人设的话喊你。
存本机,重启不丢。
"""
import json
import time
import uuid

from paths import support_path


class ReminderStore:
    def __init__(self):
        self._path = support_path("reminders.json")
        self._items = []   # [{"id","text","due"(时间戳),"done"}]
        self.load()

    def add(self, text, due_ts):
        self._items.append({
            "id": uuid.uuid4().hex[:8],
            "text": text.strip(),
            "due": float(due_ts),
            "done": False,
        })
        self.save()

    def remove(self, rid):
        self._items = [x for x in self._items if x["id"] != rid]
        self.save()

    def all(self):
        return sorted(self._items, key=lambda x: x["due"])

    def due_now(self):
        """返回已到时间、还没提醒过的项,并标记为已提醒。"""
        now = time.time()
        fired = []
        for x in self._items:
            if not x["done"] and x["due"] <= now:
                x["done"] = True
                fired.append(x)
        if fired:
            self.save()
        return fired

    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._items = json.load(f)
        except Exception:
            self._items = []


reminders = ReminderStore()
