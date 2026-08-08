"""桌宠本体(Windows 版)。

透明无边框窗口贴在桌面右下角,循环播放待机动画,
偶尔穿插小动作、来回走动;可拖动;右键或托盘菜单打开聊天/设置。

移植自 Mac 版的 PetView / MovementController / BehaviorScheduler 的核心行为。
"""
import os
import random
import sys

from PySide6.QtCore import Qt, QTimer, QPoint, QSize
from PySide6.QtGui import QPixmap, QIcon, QAction, QTransform
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QSystemTrayIcon,
)

import animation
from paths import images_dir
from settings import settings
from chat_window import ChatWindow
from settings_window import SettingsWindow
from pomodoro_window import PomodoroWindow
from companion_window import CompanionWindow
from reminder_window import ReminderWindow
from role_lines import role_lines
from companion_record import companion
from reminder_store import reminders
import activity_monitor
from battery_monitor import BatteryWatcher
from weather_monitor import weather
from mood_system import mood
import festival_events
import system_monitor
from lock_monitor import LockWatcher
from failure_log import failure_log


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
        self._pomodoro = None
        self._companion = None
        self._reminder_win = None

        # 系统状态监控
        self._battery = BatteryWatcher()
        self._activity = "other"       # 当前判定的活动
        self._activity_locked = False  # 拖动/说话时不被活动状态覆盖
        self._sleeping = False         # 是否因长时间无操作在睡觉
        self._lock = LockWatcher()

        # 点击检测(区分"点一下说话"和"拖动")
        self._press_pos = None
        self._press_global = None
        self._moved = False
        self._click_streak = 0
        self._click_reset_timer = QTimer(self)
        self._click_reset_timer.setSingleShot(True)
        self._click_reset_timer.timeout.connect(self._reset_click_streak)

        # 气泡
        from speech_bubble import SpeechBubble
        self._bubble = SpeechBubble()

        self._set_state("idle")
        self._placed = False

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

        # 看门狗:每秒强制把角色夹回屏幕内(应对拖出、换显示器、改分辨率等一切情况)
        self._guard_timer = QTimer(self)
        self._guard_timer.timeout.connect(self._clamp_on_screen)
        self._guard_timer.start(1000)

        self._build_tray()

        # 台词预生成(后台,按人设)
        role_lines.generate_if_needed()

        # 开场问候:按时间段 + 里程碑
        QTimer.singleShot(1500, self._startup_greeting)

        # 偶尔自言自语
        self._chatter_timer = QTimer(self)
        self._chatter_timer.timeout.connect(self._maybe_chatter)
        self._chatter_timer.start(90000)   # 每 90 秒掷一次骰子

        # 看你在用什么软件(每 4 秒看一次当前最前的程序)
        self._activity_timer = QTimer(self)
        self._activity_timer.timeout.connect(self._check_activity)
        self._activity_timer.start(4000)

        # 电量(每 60 秒)
        self._battery_timer = QTimer(self)
        self._battery_timer.timeout.connect(self._check_battery)
        self._battery_timer.start(60000)

        # 提醒到点检查(每 20 秒)
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start(20000)

        # 天气(启动拉一次,之后每 30 分钟)
        weather.set_callback(self._on_weather_change)
        weather.fetch_async()
        self._weather_timer = QTimer(self)
        self._weather_timer.timeout.connect(weather.fetch_async)
        self._weather_timer.start(30 * 60 * 1000)

        # 心情(每 2 分钟重估)
        self._mood_timer = QTimer(self)
        self._mood_timer.timeout.connect(self._reevaluate_mood)
        self._mood_timer.start(120000)

        # 空闲检测(每 15 秒):人离开一阵就睡觉,回来就醒
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._check_idle)
        self._idle_timer.start(15000)

        # 锁屏/解锁检测(每 5 秒)
        self._lock_timer = QTimer(self)
        self._lock_timer.timeout.connect(self._check_lock)
        self._lock_timer.start(5000)

        # 自然眨眼(每几秒随机一次)
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._natural_blink)
        self._blink_timer.start(5000)

        # 失败含糊提示(每 10 分钟看一次要不要提)
        self._failure_timer = QTimer(self)
        self._failure_timer.timeout.connect(self._maybe_failure_hint)
        self._failure_timer.start(600000)

    # ---------------- 台词 ----------------
    def say_scene(self, scene, duration_ms=5000):
        text = role_lines.line(scene)
        if not text:
            return
        cx = self.x() + self.width() // 2
        self._bubble.show_text(text, cx, self.y(), duration_ms)

    def _startup_greeting(self):
        import datetime
        h = datetime.datetime.now().hour
        # 节日 > 认识纪念日 > 按时段问候
        fest = festival_events.festival_greeting_today()
        if fest:
            cx = self.x() + self.width() // 2
            self._bubble.show_text(fest, cx, self.y(), 6000)
            return
        milestone = companion.milestone_greeting_if_any()
        if milestone:
            cx = self.x() + self.width() // 2
            self._bubble.show_text(milestone, cx, self.y(), 6000)
            return
        if 5 <= h < 12:
            scene = "greet_morning"
        elif 12 <= h < 17:
            scene = "greet_afternoon"
        elif 17 <= h < 23:
            scene = "greet_evening"
        else:
            scene = "greet_night"
        self.say_scene(scene)

    def _maybe_chatter(self):
        if self._dragging or self._walking or self._bubble.isVisible() or self._sleeping:
            return
        # 先看有没有节日
        fest = festival_events.festival_greeting_today()
        if fest:
            cx = self.x() + self.width() // 2
            self._bubble.show_text(fest, cx, self.y(), 6000)
            return
        # 稀有事件(极低概率)
        rare = festival_events.rare_event_line()
        if rare:
            line = role_lines.line("rare") or rare
            cx = self.x() + self.width() // 2
            self._bubble.show_text(line, cx, self.y(), 6000)
            return
        import datetime
        h = datetime.datetime.now().hour
        # 心情影响开口概率:话多的心情倍率小 -> 概率高
        base = 0.25 / max(0.3, mood.chatter_multiplier)
        if random.random() < base:
            scene = "night" if (h >= 23 or h < 5) else "chatter"
            self.say_scene(scene)

    def _reset_click_streak(self):
        self._click_streak = 0

    # ---------------- 系统状态反应 ----------------
    def _busy(self):
        """正在被拖、走动、说话时,不让系统状态覆盖当前动作。"""
        return self._dragging or self._walking or self._bubble.isVisible()

    def _check_activity(self):
        if not settings.get("watch_activity"):
            return
        kind = activity_monitor.current_activity()
        if kind == self._activity:
            return
        self._activity = kind
        # 换姿势(除非正忙)
        if not self._busy():
            state = activity_monitor.ACTIVITY_STATE.get(kind, "idle")
            self._set_state(state)
        # 偶尔就着当前活动说一句(不是每次都说,免得烦)
        scene = activity_monitor.ACTIVITY_SCENE.get(kind)
        if scene and random.random() < 0.4 and not self._bubble.isVisible():
            self.say_scene(scene)

    def _check_battery(self):
        if not settings.get("watch_battery"):
            return
        if self._battery.check():
            self.say_scene("battery_low", 6000)

    def _check_reminders(self):
        for item in reminders.due_now():
            text = role_lines.line("reminder_due") or "到点了"
            full = f"{text}——{item['text']}"
            cx = self.x() + self.width() // 2
            self._bubble.show_text(full, cx, self.y(), 8000)
            self._tray.showMessage("桌宠提醒", item["text"],
                                   QSystemTrayIcon.Information, 8000)

    def _on_weather_change(self, kind):
        if self._busy():
            return
        pose = {"rain": "rain", "snow": "snow", "clear": "sunny"}.get(kind)
        if not pose:
            return
        self._set_state(pose)
        if kind == "rain":
            self.say_scene("weather_rain", 6000)
        elif kind == "snow":
            self.say_scene("weather_snow", 6000)
        # 看完天气姿势过一会儿回待机
        QTimer.singleShot(6000, lambda: self._set_state("idle")
                          if not self._busy() and not self._sleeping else None)

    def _reevaluate_mood(self):
        is_pomo = (self._pomodoro is not None
                   and getattr(self._pomodoro, "_state", "idle") in ("focus", "break"))
        mood.reevaluate(is_pomo, self._activity, weather.current)

    def _check_idle(self):
        secs = system_monitor.idle_seconds()
        threshold = int(settings.get("idle_sleep_seconds"))
        if secs >= threshold and not self._sleeping and not self._dragging:
            self._sleeping = True
            self._set_state("sleep")
        elif secs < threshold and self._sleeping:
            self._sleeping = False
            self.say_scene("greet_afternoon", 3000)  # 醒来打个招呼
            self._set_state("idle")

    def _check_lock(self):
        just_locked, just_unlocked = self._lock.poll()
        if just_locked:
            self._sleeping = True
            self._set_state("sleep")
        elif just_unlocked:
            self._sleeping = False
            self._set_state("idle")
            self.say_scene("greet_afternoon", 4000)

    def _natural_blink(self):
        # 只在安静待机时眨,别打断其它动作
        if self._state == "idle" and not self._busy() and not self._sleeping:
            if random.random() < 0.6:
                self._set_state("blink")
        # 下一次间隔随机化一点
        self._blink_timer.setInterval(random.randint(4000, 9000))

    def _maybe_failure_hint(self):
        if self._busy() or self._sleeping:
            return
        if failure_log.should_hint():
            line = role_lines.line("rare") or "好像忘了什么"
            cx = self.x() + self.width() // 2
            self._bubble.show_text(line, cx, self.y(), 5000)

    # ---------------- 素材 ----------------
    def _load_pixmap(self, path):
        key = (path, self._facing_left, round(self._scale, 3))
        if key in self._pixmap_cache:
            return self._pixmap_cache[key]
        pm = QPixmap(path)
        if not pm.isNull():
            screen = self.screen() or QApplication.primaryScreen()
            dpr = screen.devicePixelRatio() or 1.0
            avail = screen.availableGeometry()

            # 目标"屏幕上看起来的高度"(逻辑像素)= 原图高 × 倍率
            target_h = pm.height() * self._scale
            # 高度不超过屏幕 40%,宽度不超过屏幕 40%,避免任何屏幕上过大
            max_h = avail.height() * 0.40
            max_w = avail.width() * 0.40
            if target_h > max_h:
                target_h = max_h
            ratio = target_h / pm.height()
            if pm.width() * ratio > max_w:
                ratio = max_w / pm.width()
                target_h = pm.height() * ratio
            target_w = pm.width() * ratio

            # 按物理像素渲染(× dpr)再标记 dpr,高分屏也清晰、且不会被二次放大
            dev_w = max(1, int(round(target_w * dpr)))
            dev_h = max(1, int(round(target_h * dpr)))
            pm = pm.scaled(dev_w, dev_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if not self._facing_left:
                pm = pm.transformed(QTransform().scale(-1, 1))
            pm.setDevicePixelRatio(dpr)
        self._pixmap_cache[key] = pm
        return pm

    def _logical_size(self, pm):
        dpr = pm.devicePixelRatio() or 1.0
        return QSize(max(1, int(round(pm.width() / dpr))),
                     max(1, int(round(pm.height() / dpr))))

    def _apply_frame(self):
        if not self._frames:
            return
        path = self._frames[self._frame_idx % len(self._frames)]
        pm = self._load_pixmap(path)
        if pm.isNull():
            return
        self._label.setPixmap(pm)
        size = self._logical_size(pm)
        self._label.resize(size)
        self.resize(size)
        self._clamp_on_screen()
        self._reposition_bubble()

    def _clamp_on_screen(self):
        """不管之前算成什么,强制把整只夹回屏幕可见区域。"""
        r = self._screen_rect()
        x = max(r.left(), min(self.x(), r.right() - self.width()))
        y = max(r.top(), min(self.y(), r.bottom() - self.height()))
        if x != self.x() or y != self.y():
            self.move(x, y)

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
        screen = self.screen() or QApplication.primaryScreen()
        return screen.availableGeometry()

    def _place_bottom_right(self):
        r = self._screen_rect()
        x = r.right() - self.width() - 40
        x = max(r.left(), min(x, r.right() - self.width()))
        self.move(x, self._ground_y())

    def showEvent(self, e):
        super().showEvent(e)
        # 窗口真正显示后再定位,这时屏幕和尺寸才准
        if not self._placed:
            self._placed = True
            self._apply_frame()          # 用真实屏幕重新渲染一次(dpr 才对)
            self._place_bottom_right()
            # 再保险:下一轮事件循环里夹一次
            QTimer.singleShot(0, self._place_bottom_right)

    def _ground_y(self):
        r = self._screen_rect()
        y = r.bottom() - self.height() - 10
        # 夹住,保证整只都在屏幕内
        return max(r.top(), min(y, r.bottom() - self.height()))

    # ---------------- 行为调度 ----------------
    def _decide_behavior(self):
        if self._dragging or self._walking or self._sleeping:
            return
        if self._state not in ("idle", "blink"):
            if not animation.loops(self._state):
                return
        # 走动概率跟随心情
        stroll = mood.stroll_tendency
        roll = random.random()
        if roll < stroll * 0.5:
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
            self._press_global = e.globalPosition().toPoint()
            self._drag_offset = e.globalPosition().toPoint() - self.pos()
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._press_global is None:
            return
        gp = e.globalPosition().toPoint()
        if not self._moved:
            # 移动超过阈值才算拖动,否则当点击
            if (gp - self._press_global).manhattanLength() > 6:
                self._moved = True
                self._dragging = True
                self._walking = False
                self.say_scene("pickup", 3000)
                self._set_state("dragged")
        if self._dragging and self._drag_offset is not None:
            p = gp - self._drag_offset
            r = self._screen_rect()
            x = max(r.left(), min(p.x(), r.right() - self.width()))
            y = max(r.top(), min(p.y(), r.bottom() - self.height()))
            self.move(x, y)
            self._reposition_bubble()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        mood.record_interaction()
        if self._sleeping:
            self._sleeping = False
        if self._moved:
            # 拖动结束,落回地面
            self._dragging = False
            self.move(self.x(), self._ground_y())
            self.say_scene("drop", 3000)
            self._set_state("idle")
        else:
            # 没移动 = 点了一下,按连点次数说不同的话
            self._click_streak += 1
            self._click_reset_timer.start(2500)
            if self._click_streak >= 6:
                scene = "click_toomuch"
            elif self._click_streak >= 3:
                scene = "click_again"
            else:
                scene = "click"
            self.say_scene(scene, 3500)
        self._press_global = None

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
        act_pomo = QAction("番茄钟…", m)
        act_pomo.triggered.connect(self.open_pomodoro)
        m.addAction(act_pomo)
        act_comp = QAction("陪伴记录…", m)
        act_comp.triggered.connect(self.open_companion)
        m.addAction(act_comp)
        act_remind = QAction("提醒…", m)
        act_remind.triggered.connect(self.open_reminders)
        m.addAction(act_remind)
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
            self._settings_win.scale_changed.connect(self._on_scale_changed)
        self._settings_win.show()
        self._settings_win.raise_()
        self._settings_win.activateWindow()

    def open_pomodoro(self):
        if self._pomodoro is None:
            self._pomodoro = PomodoroWindow()
            self._pomodoro.focus_started.connect(lambda: self.say_scene("pomodoro_start"))
            self._pomodoro.focus_ended.connect(lambda: self.say_scene("pomodoro_end", 6000))
            self._pomodoro.break_started.connect(lambda: self.say_scene("break_start"))
            self._pomodoro.break_ended.connect(lambda: self.say_scene("break_end", 6000))
        self._pomodoro.show()
        self._pomodoro.raise_()
        self._pomodoro.activateWindow()

    def open_companion(self):
        if self._companion is None:
            self._companion = CompanionWindow()
        self._companion.show()
        self._companion.raise_()
        self._companion.activateWindow()

    def open_reminders(self):
        if self._reminder_win is None:
            self._reminder_win = ReminderWindow()
        self._reminder_win.show()
        self._reminder_win.raise_()
        self._reminder_win.activateWindow()

    def _on_settings_changed(self):
        if self._chat is not None:
            self._chat.refresh_status()

    def _on_scale_changed(self, scale):
        """设置里拖动大小滑块时,实时缩放并落回地面。"""
        self._scale = float(scale)
        self._pixmap_cache.clear()
        self._apply_frame()
        self.move(self.x(), self._ground_y())
        self._reposition_bubble()

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
