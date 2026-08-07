"""聊天窗口。

AI 请求放到 QThread 后台线程,回来用信号更新界面,避免卡住 UI。
"""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel,
)

import ai_service
from conversation import conversation
from companion_record import companion


class _SendWorker(QThread):
    done = Signal(str, bool)   # (回复, 是不是AI给的)

    def __init__(self, text):
        super().__init__()
        self._text = text

    def run(self):
        reply, from_ai = ai_service.send(self._text)
        self.done.emit(reply, from_ai)


class ChatWindow(QWidget):
    # 让主程序能在收到回复时联动角色动画(说话/思考)
    thinking = Signal()
    replied = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("聊天")
        self.resize(420, 560)
        self._worker = None

        layout = QVBoxLayout(self)

        self._status = QLabel(ai_service.status_text())
        self._status.setStyleSheet("color:#888; font-size:12px;")
        layout.addWidget(self._status)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log, 1)

        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("说点什么…(回车发送)")
        self._input.returnPressed.connect(self._on_send)
        row.addWidget(self._input, 1)
        self._send_btn = QPushButton("发送")
        self._send_btn.clicked.connect(self._on_send)
        row.addWidget(self._send_btn)
        layout.addLayout(row)

        clear_btn = QPushButton("清空聊天记录")
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn)

        self._restore_history()

    def refresh_status(self):
        self._status.setText(ai_service.status_text())

    def _restore_history(self):
        for m in conversation.messages:
            who = "你" if m["role"] == "user" else "它"
            self._append_line(who, m["content"])

    def _append_line(self, who, text):
        color = "#4a90d9" if who == "你" else "#e07b53"
        self._log.append(f'<b style="color:{color}">{who}:</b> {self._escape(text)}')
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum())

    @staticmethod
    def _escape(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace("\n", "<br>"))

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()
        self._append_line("你", text)
        self._send_btn.setEnabled(False)
        self._send_btn.setText("…")
        self.thinking.emit()

        self._worker = _SendWorker(text)
        self._worker.done.connect(self._on_reply)
        self._worker.start()

    def _on_reply(self, reply, from_ai):
        self._append_line("它", reply)
        companion.note_chat()
        self._send_btn.setEnabled(True)
        self._send_btn.setText("发送")
        self._worker = None
        self.replied.emit(reply)

    def _on_clear(self):
        conversation.clear()
        self._log.clear()
