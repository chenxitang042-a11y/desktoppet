"""说话气泡。一个无边框半透明小窗,浮在角色上方。"""
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPainterPath, QFontMetrics
from PySide6.QtWidgets import QWidget


class SpeechBubble(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._text = ""
        self._max_w = 260
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text, anchor_center_x, anchor_top_y, duration_ms=6000):
        self._text = (text or "").strip()
        if not self._text:
            self.hide()
            return
        self._layout(anchor_center_x, anchor_top_y)
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)

    def _layout(self, cx, top_y):
        font = QFont()
        font.setPointSize(11)
        fm = QFontMetrics(font)
        # 折行
        words = self._text
        rect = fm.boundingRect(0, 0, self._max_w - 24, 2000,
                               Qt.TextWordWrap, words)
        w = min(self._max_w, rect.width() + 24)
        h = rect.height() + 22
        self._box_w, self._box_h = w, h
        x = int(cx - w / 2)
        y = int(top_y - h - 8)
        self.setGeometry(x, y, w, h + 8)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self._box_w, self._box_h
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 12, 12)
        # 小尾巴
        path.moveTo(w / 2 - 8, h - 2)
        path.lineTo(w / 2, h + 6)
        path.lineTo(w / 2 + 8, h - 2)
        p.fillPath(path, QColor(255, 255, 255, 240))
        p.setPen(QColor(0, 0, 0, 30))
        p.drawPath(path)

        p.setPen(QColor(40, 40, 40))
        f = QFont()
        f.setPointSize(11)
        p.setFont(f)
        p.drawText(QRectF(12, 10, w - 24, h - 18),
                   Qt.TextWordWrap, self._text)
