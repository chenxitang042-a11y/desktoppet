"""番茄钟。桌宠陪你专注。

专注倒计时结束 -> 提醒休息;休息结束 -> 问是否继续。
每个阶段切换时发信号,让角色冒一句符合人设的话。
"""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
)


class PomodoroWindow(QWidget):
    # 阶段切换信号,主程序接过去让角色说话
    focus_started = Signal()
    focus_ended = Signal()
    break_started = Signal()
    break_ended = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("番茄钟")
        self.resize(300, 300)

        self._state = "idle"     # idle / focus / break / paused
        self._paused_from = None
        self._remaining = 0

        v = QVBoxLayout(self)

        # 时长设置
        row = QHBoxLayout()
        row.addWidget(QLabel("专注"))
        self._focus_min = QSpinBox()
        self._focus_min.setRange(1, 180)
        self._focus_min.setValue(25)
        self._focus_min.setSuffix(" 分")
        row.addWidget(self._focus_min)
        row.addSpacing(12)
        row.addWidget(QLabel("休息"))
        self._break_min = QSpinBox()
        self._break_min.setRange(1, 60)
        self._break_min.setValue(5)
        self._break_min.setSuffix(" 分")
        row.addWidget(self._break_min)
        v.addLayout(row)

        # 倒计时大字
        self._display = QLabel("25:00")
        self._display.setAlignment(Qt.AlignCenter)
        self._display.setStyleSheet("font-size:56px; font-weight:bold; margin:16px;")
        v.addWidget(self._display)

        self._phase_label = QLabel("准备开始")
        self._phase_label.setAlignment(Qt.AlignCenter)
        self._phase_label.setStyleSheet("color:#888;")
        v.addWidget(self._phase_label)

        # 按钮
        btns = QHBoxLayout()
        self._start_btn = QPushButton("开始专注")
        self._start_btn.clicked.connect(self._on_start_pause)
        btns.addWidget(self._start_btn)
        self._reset_btn = QPushButton("重置")
        self._reset_btn.clicked.connect(self._on_reset)
        btns.addWidget(self._reset_btn)
        v.addLayout(btns)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(1000)

    # ---- 控制 ----
    def _on_start_pause(self):
        if self._state == "idle":
            self._begin_focus()
        elif self._state in ("focus", "break"):
            self._pause()
        elif self._state == "paused":
            self._resume()

    def _begin_focus(self):
        self._state = "focus"
        self._remaining = self._focus_min.value() * 60
        self._focus_min.setEnabled(False)
        self._break_min.setEnabled(False)
        self._phase_label.setText("专注中")
        self._start_btn.setText("暂停")
        self._timer.start()
        self._update_display()
        self.focus_started.emit()

    def _begin_break(self):
        self._state = "break"
        self._remaining = self._break_min.value() * 60
        self._phase_label.setText("休息中")
        self._start_btn.setText("暂停")
        self._timer.start()
        self._update_display()
        self.break_started.emit()

    def _pause(self):
        self._paused_from = self._state
        self._state = "paused"
        self._timer.stop()
        self._start_btn.setText("继续")
        self._phase_label.setText("已暂停")

    def _resume(self):
        self._state = self._paused_from or "focus"
        self._start_btn.setText("暂停")
        self._phase_label.setText("专注中" if self._state == "focus" else "休息中")
        self._timer.start()

    def _on_reset(self):
        self._timer.stop()
        self._state = "idle"
        self._focus_min.setEnabled(True)
        self._break_min.setEnabled(True)
        self._remaining = self._focus_min.value() * 60
        self._start_btn.setText("开始专注")
        self._phase_label.setText("准备开始")
        self._update_display()

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            if self._state == "focus":
                self._timer.stop()
                self.focus_ended.emit()
                self._begin_break()
            elif self._state == "break":
                self._timer.stop()
                self.break_ended.emit()
                self._on_reset()
            return
        self._update_display()

    def _update_display(self):
        m, s = divmod(max(0, self._remaining), 60)
        self._display.setText(f"{m:02d}:{s:02d}")
