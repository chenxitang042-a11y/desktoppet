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
        self.setFixedSize(340, 380)

        self._state = "idle"     # idle / focus / break / paused
        self._paused_from = None
        self._remaining = 0
        self._focus_elapsed = 0  # 本次番茄钟累计已专注秒数(暂停不计,休息不计)

        # 统一样式:微软雅黑、单一蓝色主色、干净留白
        ACCENT = "#3E7BD6"
        self.setStyleSheet(f"""
            QWidget {{
                background: #FFFFFF;
                font-family: "Microsoft YaHei", "微软雅黑", sans-serif;
                color: #333333;
            }}
            QLabel {{ background: transparent; }}
            QSpinBox {{
                font-size: 15px;
                padding: 4px 6px;
                border: 1px solid #D8DEE8;
                border-radius: 6px;
                background: #FFFFFF;
                min-width: 64px;
            }}
            QSpinBox:disabled {{ color: #AAAAAA; background: #F4F6F9; }}
            QPushButton {{
                font-size: 15px;
                font-weight: bold;
                padding: 10px 0;
                border: none;
                border-radius: 8px;
                background: {ACCENT};
                color: #FFFFFF;
            }}
            QPushButton:hover {{ background: #3468BC; }}
            QPushButton#ghost {{
                background: #F2F4F8;
                color: #555555;
                font-weight: normal;
            }}
            QPushButton#ghost:hover {{ background: #E6EAF1; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(0)

        # 时长设置
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl_focus = QLabel("专注")
        lbl_focus.setStyleSheet("font-size:14px; color:#666666;")
        row.addWidget(lbl_focus)
        self._focus_min = QSpinBox()
        self._focus_min.setRange(1, 180)
        self._focus_min.setValue(25)
        self._focus_min.setSuffix(" 分")
        row.addWidget(self._focus_min)
        row.addStretch(1)
        lbl_break = QLabel("休息")
        lbl_break.setStyleSheet("font-size:14px; color:#666666;")
        row.addWidget(lbl_break)
        self._break_min = QSpinBox()
        self._break_min.setRange(1, 60)
        self._break_min.setValue(5)
        self._break_min.setSuffix(" 分")
        row.addWidget(self._break_min)
        root.addLayout(row)

        root.addSpacing(24)

        # 倒计时大字
        self._display = QLabel("25:00")
        self._display.setAlignment(Qt.AlignCenter)
        self._display.setStyleSheet(
            f"font-size:68px; font-weight:bold; color:{ACCENT}; letter-spacing:2px;")
        root.addWidget(self._display)

        # 阶段状态
        self._phase_label = QLabel("准备开始")
        self._phase_label.setAlignment(Qt.AlignCenter)
        self._phase_label.setStyleSheet("font-size:15px; color:#888888; margin-top:2px;")
        root.addWidget(self._phase_label)

        root.addSpacing(6)

        # 已用时间(从开始专注到现在累计过了多久)
        self._elapsed_label = QLabel("已专注 00:00")
        self._elapsed_label.setAlignment(Qt.AlignCenter)
        self._elapsed_label.setStyleSheet("font-size:14px; color:#AAAAAA;")
        root.addWidget(self._elapsed_label)

        root.addStretch(1)

        # 按钮
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self._start_btn = QPushButton("开始专注")
        self._start_btn.clicked.connect(self._on_start_pause)
        btns.addWidget(self._start_btn, 2)
        self._reset_btn = QPushButton("重置")
        self._reset_btn.setObjectName("ghost")
        self._reset_btn.clicked.connect(self._on_reset)
        btns.addWidget(self._reset_btn, 1)
        root.addLayout(btns)

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
        self._focus_elapsed = 0
        self._focus_min.setEnabled(False)
        self._break_min.setEnabled(False)
        self._phase_label.setText("专注中")
        self._start_btn.setText("暂停")
        self._timer.start()
        self._update_display()
        self._update_elapsed()
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
        self._focus_elapsed = 0
        self._focus_min.setEnabled(True)
        self._break_min.setEnabled(True)
        self._remaining = self._focus_min.value() * 60
        self._start_btn.setText("开始专注")
        self._phase_label.setText("准备开始")
        self._update_display()
        self._update_elapsed()

    def _tick(self):
        # 只在专注阶段累计"已专注"时间
        if self._state == "focus":
            self._focus_elapsed += 1
            self._update_elapsed()
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

    def _update_elapsed(self):
        m, s = divmod(max(0, self._focus_elapsed), 60)
        self._elapsed_label.setText(f"已专注 {m:02d}:{s:02d}")

    def _update_display(self):
        m, s = divmod(max(0, self._remaining), 60)
        self._display.setText(f"{m:02d}:{s:02d}")
