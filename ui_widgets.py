"""精致的自定义控件:iOS 风格开关、分段选择、圆角卡片、滑块行。

全部用抗锯齿手绘,保证不像素化;统一微软雅黑 + 单一蓝色主色。
"""
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, Property, Signal
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSlider, QButtonGroup, QPushButton,
)

ACCENT = "#3E7BD6"
FONT = '"Microsoft YaHei", "微软雅黑", sans-serif'


class ToggleSwitch(QAbstractButton):
    """手绘的圆角开关。"""
    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self.toggled.connect(self._animate)

    def _get_knob(self):
        return self._pos

    def _set_knob(self, v):
        self._pos = v
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # 轨道
        off = QColor("#C9CFD8")
        on = QColor(ACCENT)
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setBrush(track)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        # 滑块
        d = h - 6
        x = 3 + self._pos * (w - d - 6)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, 3, d, d))


class Segmented(QWidget):
    """分段选择:一排按钮,只有一个选中。"""
    changed = Signal(str)   # 发出选中项的 key

    def __init__(self, options, current=None):
        # options: [(key, label), ...]
        super().__init__()
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._keys = []
        for i, (key, label) in enumerate(options):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            edge = ""
            if i == 0:
                edge = "border-top-left-radius:8px;border-bottom-left-radius:8px;"
            if i == len(options) - 1:
                edge += "border-top-right-radius:8px;border-bottom-right-radius:8px;"
            b.setStyleSheet(f"""
                QPushButton {{
                    font-family:{FONT}; font-size:14px;
                    padding:7px 14px; border:1px solid #D8DEE8;
                    background:#FFFFFF; color:#555; {edge}
                }}
                QPushButton:checked {{
                    background:{ACCENT}; color:#FFFFFF; border-color:{ACCENT};
                }}
            """)
            if key == current:
                b.setChecked(True)
            self._group.addButton(b, i)
            self._keys.append(key)
            lay.addWidget(b)
        self._group.idClicked.connect(
            lambda idx: self.changed.emit(self._keys[idx]))


class Card(QFrame):
    """圆角卡片容器。"""
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #ECEFF3;border-radius:12px;}")
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(18, 6, 18, 6)
        self._v.setSpacing(0)

    def add_row(self, widget):
        self._v.addWidget(widget)

    def add_divider(self):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#F0F2F5;border:none;")
        self._v.addWidget(line)


class Row(QWidget):
    """一行:左标题(可带副标题),右控件。"""
    def __init__(self, title, control, subtitle=None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"font-family:{FONT};font-size:15px;color:#2B2F36;background:transparent;")
        left.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"font-family:{FONT};font-size:12px;color:#9AA1AB;background:transparent;")
            s.setWordWrap(True)
            left.addWidget(s)
        lay.addLayout(left, 1)
        if control is not None:
            lay.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)


class SliderRow(QWidget):
    """标题 + 滑块 + 右侧数值。"""
    changed = Signal(int)

    def __init__(self, title, minimum, maximum, value, suffix=""):
        super().__init__()
        self._suffix = suffix
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        t = QLabel(title)
        t.setStyleSheet(f"font-family:{FONT};font-size:15px;color:#2B2F36;background:transparent;")
        lay.addWidget(t)
        lay.addSpacing(12)
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(minimum)
        self._slider.setMaximum(maximum)
        self._slider.setValue(value)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height:4px; background:#E3E7ED; border-radius:2px; }}
            QSlider::sub-page:horizontal {{ background:{ACCENT}; border-radius:2px; }}
            QSlider::handle:horizontal {{
                background:#FFFFFF; border:2px solid {ACCENT};
                width:16px; height:16px; margin:-7px 0; border-radius:9px;
            }}
        """)
        lay.addWidget(self._slider, 1)
        lay.addSpacing(10)
        self._val = QLabel(self._fmt(value))
        self._val.setFixedWidth(56)
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._val.setStyleSheet(f"font-family:{FONT};font-size:14px;color:#555;background:transparent;")
        lay.addWidget(self._val)
        self._slider.valueChanged.connect(self._on_change)

    def _fmt(self, v):
        return f"{v}{self._suffix}"

    def _on_change(self, v):
        self._val.setText(self._fmt(v))
        self.changed.emit(v)


def section_title(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-family:{FONT};font-size:16px;font-weight:bold;color:#1F2933;"
        "background:transparent;margin-top:6px;")
    return lbl


def hint_label(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"font-family:{FONT};font-size:12px;color:#9AA1AB;background:transparent;")
    return lbl
