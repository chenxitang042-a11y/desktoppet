"""聊天:小悬浮输入框 + 聊天记录窗。

- ChatInput:很小的悬浮框,可任意拖动,输入后角色用气泡回话。
- ChatHistoryWindow:查看/搜索聊天记录,每句下面显示时刻,可刷新/导出/清空。
"""
import os
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QScrollArea, QFrame,
)

import ai_service
from conversation import conversation
from companion_record import companion
from paths import support_dir

ACCENT = "#3E7BD6"
FONT = ('"Microsoft YaHei", "微软雅黑", "PingFang SC", '
        '-apple-system, "Segoe UI", sans-serif')


class _SendWorker(QThread):
    done = Signal(str, bool)

    def __init__(self, text):
        super().__init__()
        self._text = text

    def run(self):
        reply, from_ai = ai_service.send(self._text)
        self.done.emit(reply, from_ai)


class ChatInput(QWidget):
    """很小的悬浮输入框,可拖动。回复由角色气泡显示。"""
    thinking = Signal()
    replied = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(440)
        self._worker = None
        self._drag = None

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background:#FFFFFF; border:1px solid #E3E6EA; border-radius:14px;
            }}
            QLineEdit {{
                border:none; background:transparent; font-family:{FONT};
                font-size:16px; padding:6px 2px; color:#1D1D1F;
            }}
            QLabel {{ font-family:{FONT}; background:transparent; }}
            QPushButton {{
                font-family:{FONT}; font-size:14px; padding:7px 16px;
                border:none; border-radius:8px; font-weight:600;
            }}
            QPushButton#say {{ background:{ACCENT}; color:#FFFFFF; }}
            QPushButton#say:hover {{ background:#3468BC; }}
            QPushButton#cancel {{ background:#EEF0F3; color:#4A4F57; font-weight:normal; }}
            QPushButton#cancel:hover {{ background:#E4E7EC; }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("想说的话…")
        self._input.returnPressed.connect(self._on_send)
        v.addWidget(self._input)

        row = QHBoxLayout()
        self._status = QLabel(ai_service.status_text())
        self._status.setStyleSheet("color:#8A8F98; font-size:12px;")
        row.addWidget(self._status, 1)
        cancel = QPushButton("取消"); cancel.setObjectName("cancel")
        cancel.clicked.connect(self.hide)
        row.addWidget(cancel)
        self._say = QPushButton("说"); self._say.setObjectName("say")
        self._say.clicked.connect(self._on_send)
        row.addWidget(self._say)
        v.addLayout(row)

    def refresh_status(self):
        self._status.setText(ai_service.status_text())

    def focus_input(self):
        self._input.setFocus()

    # 拖动整个框
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._say.setEnabled(False)
        self._say.setText("…")
        self.thinking.emit()
        self._worker = _SendWorker(text)
        self._worker.done.connect(self._on_reply)
        self._worker.start()

    def _on_reply(self, reply, from_ai):
        companion.note_chat()
        self._say.setEnabled(True)
        self._say.setText("说")
        self._worker = None
        self.replied.emit(reply)
        self.refresh_status()


class ChatHistoryWindow(QWidget):
    """聊天记录:搜索 + 每句时刻 + 刷新/导出/清空。"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("聊天记录")
        self.resize(460, 620)
        self.setStyleSheet(f"""
            QWidget {{ background:#F2F3F5; font-family:{FONT}; color:#33353A; }}
            QLineEdit {{ background:#FFFFFF; border:1px solid #DFE2E7;
                border-radius:8px; padding:8px 10px; font-size:14px; }}
            QLineEdit:focus {{ border-color:{ACCENT}; }}
            QScrollArea {{ border:none; background:#F2F3F5; }}
            QPushButton {{ font-size:14px; padding:8px 14px; border:none;
                border-radius:8px; background:#EEF0F3; color:#4A4F57; }}
            QPushButton:hover {{ background:#E4E7EC; }}
            QPushButton#danger {{ background:#FCECEC; color:#C0392B; }}
            QPushButton#danger:hover {{ background:#F7DCDC; }}
            QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
            QScrollBar::handle:vertical {{ background:#CFD3D9; border-radius:5px; min-height:30px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
        """)

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        top = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索聊过的内容")
        self._search.textChanged.connect(self._render)
        top.addWidget(self._search, 1)
        self._count = QLabel("")
        self._count.setStyleSheet("color:#8A8F98; font-size:12px;")
        top.addWidget(self._count)
        v.addLayout(top)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._inner = QWidget()
        self._list = QVBoxLayout(self._inner)
        self._list.setContentsMargins(2, 2, 2, 2)
        self._list.setSpacing(10)
        self._list.addStretch(1)
        self._scroll.setWidget(self._inner)
        v.addWidget(self._scroll, 1)

        bottom = QHBoxLayout()
        if conversation.summary:
            note = QLabel("更早的对话已压成概要")
            note.setStyleSheet("color:#8A8F98; font-size:12px;")
            bottom.addWidget(note)
        bottom.addStretch(1)
        refresh = QPushButton("刷新"); refresh.clicked.connect(self._render)
        bottom.addWidget(refresh)
        export = QPushButton("导出"); export.clicked.connect(self._export)
        bottom.addWidget(export)
        clear = QPushButton("全部清空"); clear.setObjectName("danger")
        clear.clicked.connect(self._clear)
        bottom.addWidget(clear)
        v.addLayout(bottom)

    def showEvent(self, e):
        self._render()
        super().showEvent(e)

    def _render(self):
        # 清空旧内容(保留末尾 stretch)
        while self._list.count() > 1:
            item = self._list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        kw = self._search.text().strip()
        msgs = conversation.messages
        shown = 0
        turns = 0
        for m in msgs:
            if m["role"] == "user":
                turns += 1
            if kw and kw not in m["content"]:
                continue
            self._list.insertWidget(self._list.count() - 1, self._bubble(m))
            shown += 1
        self._count.setText(f"{turns} 轮 · {len(msgs)} 条")

    def _bubble(self, m):
        is_user = m["role"] == "user"
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        bubble = QLabel(m["content"])
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(340)
        if is_user:
            bubble.setStyleSheet(
                f"background:{ACCENT}; color:#FFFFFF; border-radius:12px;"
                "padding:10px 12px; font-size:14px;")
        else:
            bubble.setStyleSheet(
                "background:#FFFFFF; color:#2B2F36; border:1px solid #E7E9ED;"
                "border-radius:12px; padding:10px 12px; font-size:14px;")
        brow = QHBoxLayout()
        brow.setContentsMargins(0, 0, 0, 0)
        if is_user:
            brow.addStretch(1)
            brow.addWidget(bubble)
        else:
            brow.addWidget(bubble)
            brow.addStretch(1)
        lay.addLayout(brow)

        ts = m.get("date")
        when = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
        tl = QLabel(when)
        tl.setStyleSheet("color:#A4A9B1; font-size:11px;")
        trow = QHBoxLayout()
        trow.setContentsMargins(4, 0, 4, 0)
        if is_user:
            trow.addStretch(1)
            trow.addWidget(tl)
        else:
            trow.addWidget(tl)
            trow.addStretch(1)
        lay.addLayout(trow)
        return wrap

    def _export(self):
        lines = []
        for m in conversation.messages:
            who = "我" if m["role"] == "user" else "它"
            ts = m.get("date")
            when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            lines.append(f"[{when}] {who}:{m['content']}")
        path = os.path.join(support_dir(), "聊天记录导出.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _clear(self):
        conversation.clear()
        self._render()
