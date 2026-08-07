"""提醒窗口。加一条"几点提醒我做什么",列出、删除。"""
import time
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QDateTimeEdit, QComboBox,
)
from PySide6.QtCore import QDateTime

from reminder_store import reminders


class ReminderWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("提醒")
        self.resize(360, 420)
        v = QVBoxLayout(self)

        v.addWidget(QLabel("让它提醒你:"))

        self._text = QLineEdit()
        self._text.setPlaceholderText("提醒我做什么,比如:起来喝水")
        v.addWidget(self._text)

        row = QHBoxLayout()
        row.addWidget(QLabel("时间"))
        self._when = QDateTimeEdit()
        self._when.setDateTime(QDateTime.currentDateTime().addSecs(1800))  # 默认半小时后
        self._when.setDisplayFormat("MM-dd HH:mm")
        self._when.setCalendarPopup(True)
        row.addWidget(self._when, 1)
        v.addLayout(row)

        quick = QHBoxLayout()
        for label, secs in [("15分钟后", 900), ("30分钟后", 1800),
                            ("1小时后", 3600), ("明早9点", None)]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, s=secs: self._quick(s))
            quick.addWidget(b)
        v.addLayout(quick)

        add_btn = QPushButton("添加提醒")
        add_btn.clicked.connect(self._on_add)
        v.addWidget(add_btn)

        v.addWidget(QLabel("已设置的提醒:"))
        self._list = QListWidget()
        v.addWidget(self._list, 1)

        del_btn = QPushButton("删除选中的")
        del_btn.clicked.connect(self._on_delete)
        v.addWidget(del_btn)

        self._refresh()

    def _quick(self, secs):
        if secs is None:
            # 明早 9 点
            t = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            if t <= datetime.now():
                t += timedelta(days=1)
            self._when.setDateTime(QDateTime(t.date().year, t.date().month, t.date().day,
                                             9, 0))
        else:
            self._when.setDateTime(QDateTime.currentDateTime().addSecs(secs))

    def _on_add(self):
        text = self._text.text().strip()
        if not text:
            return
        due = self._when.dateTime().toSecsSinceEpoch()
        reminders.add(text, due)
        self._text.clear()
        self._refresh()

    def _on_delete(self):
        item = self._list.currentItem()
        if item is None:
            return
        rid = item.data(Qt.UserRole)
        reminders.remove(rid)
        self._refresh()

    def _refresh(self):
        self._list.clear()
        for x in reminders.all():
            when = datetime.fromtimestamp(x["due"]).strftime("%m-%d %H:%M")
            status = "✓ " if x["done"] else ""
            it = QListWidgetItem(f"{status}{when}  {x['text']}")
            it.setData(Qt.UserRole, x["id"])
            self._list.addItem(it)

    def showEvent(self, e):
        self._refresh()
        super().showEvent(e)
