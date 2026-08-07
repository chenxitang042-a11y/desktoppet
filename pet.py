"""桌宠本体(Windows 版)。

透明无边框窗口贴在桌面右下角,循环播放待机动画,
偶尔穿插小动作、来回走动;可拖动;右键或托盘菜单打开聊天/设置。

移植自 Mac 版的 PetView / MovementController / BehaviorScheduler 的核心行为。
"""
import os
import random
import sys

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPixmap, QIcon, QAction, QTransform
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QSystemTrayIcon,
)

import animation
from paths import images_dir
from settings import settings
from chat_window import ChatWindow
from settings_window import SettingsWindow


class Pet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._label = QLabel(self)
        self._label.setAttribute(Qt.WA_TranslucentBackground)

        self._scale = float(settings.get("pet_scale"))
        self._facing_left = True   # 素材默认朝左;向右走时水平翻转
        self._pixmap_cache = {}

        # 动画状态
        self._state = "idle"
        self._frames = []
        self._frame_idx = 0

        # 走动
        self._walking = False
        self._walk_target_x = None
        self._walk_speed = 2

        # 拖动
        self._drag_offset = None
        self._dragging = False

        # 子窗口(延迟创建)
        self._chat = None
        self._settings_win = None

        # 气泡
        from speech_bubble import SpeechBubble
        self._bubble = SpeechBubble()

        self._set_state("idle")
        self._place_bottom_right()

        # 帧推进定时器
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._advance_frame)
        self._frame_timer.start(animation.frame_interval("idle"))

        # 行为调度:每隔几秒决定下一步做什么
        self._behavior_timer = QTimer(self)
        self._behavior_timer.timeout.connect(self._decide_behavior)
        self._behavior_timer.start(4000)

        # 走动步进
        self._move_timer = QTimer(self)
        self._move_timer.timeout.connect(self._step_walk)
        self._move_timer.start(30)

        self._build_tray()

    # ---------------- 素材 ----------------
    def _load_pixmap(self, path):
        key = (path, self._facing_left)
        if key in self._pixmap_cache:
            return self._pixmap_cache[key]
        pm = QPixmap(path)
        if not pm.isNull():
            w = int(pm.width() * self._scale)
            h = int(pm.height() * self._scale)
            pm = pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not self._facing_left:
                pm = pm.transformed(QTransform().scale(-1, 1))
        self._pixmap_cache[key] = pm
        return pm

    def _apply_frame(self):
        if not self._frames:
            return
        path = self._frames[self._frame_idx % len(self._frames)]
        pm = self._load_pixmap(path)
        if pm.isNull():
            return
        self._label.setPixmap(pm)
        self._label.resize(pm.size())
        self.resize(pm.size())
        self._reposition_bubble()

    def _set_state(self, state):
        self._state = state
        self._frames = animation.frame_paths(state)
        self._frame_idx = 0
        if hasattr(self, "_frame_timer"):
            self._frame_timer.setInterval(animation.frame_interval(state))
        self._apply_frame()

    def _advance_frame(self):
        if not self._frames:
            return
        self._frame_idx += 1
        if self._frame_idx >= len(self._frames):
            if animation.loops(self._state):
                self._frame_idx = 0
            else:
                # 非循环动作(眨眼/挥手/伸懒腰)播完回到待机
                self._frame_idx = len(self._frames) - 1
                if not self._walking and self._state not in ("idle", "dragged"):
                    QTimer.singleShot(200, lambda: self._set_state("idle")
                                      if not self._dragging and not self._walking
                                      else None)
                return
        self._apply_frame()

    # ---------------- 位置 ----------------
    def _screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()

    def _place_bottom_right(self):
        r = self._screen_rect()
        self.move(r.right() - self.width() - 40, r.bottom() - self.height() - 10)

    def _ground_y(self):
        return self._screen_rect().bottom() - self.height() - 10

    # ---------------- 行为调度 ----------------
    def _decide_behavior(self):
        if self._dragging or self._walking:
            return
        if self._state not in ("idle", "blink"):
            # 正在做某个小动作,先不打断
            if not animation.loops(self._state):
                return
        roll = random.random()
        if roll < 0.35:
            self._start_walk()
        elif roll < 0.85:
            self._set_state(random.choice(animation.IDLE_BEHAVIORS))
        else:
            self._set_state("idle")

    # ---------------- 走动 ----------------
    def _start_walk(self):
        r = self._screen_rect()
        margin = 40
        target = random.randint(r.left() + margin, r.right() - self.width() - margin)
        if abs(target - self.x()) < 60:
            return
        self._walk_target_x = target
        self._facing_left = target < self.x()
        self._pixmap_cache.clear()  # 朝向变了,缓存作废
        self._walking = True
        self._set_state("walk")

    def _step_walk(self):
        if not self._walking or self._walk_target_x is None or self._dragging:
            return
        x = self.x()
        dx = self._walk_target_x - x
        if abs(dx) <= self._walk_speed:
            self.move(self._walk_target_x, self._ground_y())
            self._walking = False
            self._walk_target_x = None
            self._set_state("idle")
            return
        step = self._walk_speed if dx > 0 else -self._walk_speed
        self.move(x + step, self._ground_y())
        self._reposition_bubble()

    # ---------------- 拖动 ----------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._walking = False
            self._drag_offset = e.globalPosition().toPoint() - self.pos()
            self._set_state("dragged")

    def mouseMoveEvent(self, e):
        if self._dragging and self._drag_offset is not None:
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            self._reposition_bubble()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            # 松手后落回地面高度
            self.move(self.x(), self._ground_y())
            self._set_state("idle")

    def contextMenuEvent(self, e):
        self._menu().exec(e.globalPos())

    # ---------------- 菜单 / 托盘 ----------------
    def _menu(self):
        m = QMenu()
        act_chat = QAction("聊天…", m)
        act_chat.triggered.connect(self.open_chat)
        m.addAction(act_chat)
        act_set = QAction("设置…", m)
        act_set.triggered.connect(self.open_settings)
        m.addAction(act_set)
        m.addSeparator()
        act_quit = QAction("退出", m)
        act_quit.triggered.connect(QApplication.quit)
        m.addAction(act_quit)
        return m

    def _build_tray(self):
        icon_path = os.path.join(images_dir(), "idle.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("桌宠")
        self._tray.setContextMenu(self._menu())
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # 左键单击托盘 → 打开聊天
            self.open_chat()

    # ---------------- 子窗口 ----------------
    def open_chat(self):
        if self._chat is None:
            self._chat = ChatWindow()
            self._chat.thinking.connect(self._on_thinking)
            self._chat.replied.connect(self._on_replied)
        self._chat.refresh_status()
        self._chat.show()
        self._chat.raise_()
        self._chat.activateWindow()

    def open_settings(self):
        if self._settings_win is None:
            self._settings_win = SettingsWindow()
            self._settings_win.changed.connect(self._on_settings_changed)
        self._settings_win.show()
        self._settings_win.raise_()
        self._settings_win.activateWindow()

    def _on_settings_changed(self):
        if self._chat is not None:
            self._chat.refresh_status()

    def _on_thinking(self):
        self._walking = False
        self._set_state("think")

    def _on_replied(self, text):
        self._set_state("talk")
        cx = self.x() + self.width() // 2
        top = self.y()
        self._bubble.show_text(text, cx, top)
        # 说完回到待机
        QTimer.singleShot(3000, lambda: self._set_state("idle")
                          if not self._dragging and not self._walking else None)

    def _reposition_bubble(self):
        if self._bubble.isVisible():
            cx = self.x() + self.width() // 2
            top = self.y()
            self._bubble._layout(cx, top)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关掉聊天窗不退出程序
    pet = Pet()
    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
