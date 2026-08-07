"""陪伴记录窗口。展示相伴天数、聊天次数等。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from companion_record import companion


class CompanionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("陪伴记录")
        self.resize(280, 220)
        self._v = QVBoxLayout(self)
        self._title = QLabel("我们的记录")
        self._title.setStyleSheet("font-size:18px; font-weight:bold; margin-bottom:8px;")
        self._v.addWidget(self._title)
        self._body = QLabel()
        self._body.setStyleSheet("font-size:14px; line-height:1.8;")
        self._v.addWidget(self._body)
        self._v.addStretch(1)

    def showEvent(self, e):
        # 每次打开刷新最新数字
        self._body.setText("\n\n".join(companion.summary_lines()))
        super().showEvent(e)
