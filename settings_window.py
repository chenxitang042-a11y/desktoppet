"""设置窗口。四个标签页:陪伴 / 对话 / 外观 / 其它。

按 Mac 版的分区和顺序排列,统一微软雅黑 + 蓝色主色 + 圆角卡片。
"""
import os
import shutil
import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QLabel,
    QLineEdit, QComboBox, QPushButton, QTextEdit, QScrollArea, QMessageBox,
)

from settings import settings
from ai_client import client, PROVIDERS, find_provider
from paths import support_dir, images_dir
from ui_widgets import (
    ACCENT, FONT, ToggleSwitch, Segmented, Card, Row, SliderRow,
    section_title, hint_label,
)

_QSS = f"""
QWidget {{ background:#F2F3F5; font-family:{FONT}; color:#33353A; }}
QScrollArea {{ border:none; background:#F2F3F5; }}
QTabWidget::pane {{ border:none; background:#F2F3F5; }}
QTabBar::tab {{
    font-family:{FONT}; font-size:13px; padding:7px 20px; margin:6px 3px;
    background:transparent; color:#7A828C; border-radius:8px;
}}
QTabBar::tab:hover {{ background:#E9EBEF; }}
QTabBar::tab:selected {{ background:#FFFFFF; color:{ACCENT}; font-weight:600;
    border:1px solid #E7E9ED; }}
QLineEdit, QComboBox, QTextEdit {{
    background:#FFFFFF; border:1px solid #DFE2E7; border-radius:8px;
    padding:7px 10px; font-size:14px; selection-background-color:{ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color:{ACCENT}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QPushButton {{
    font-size:14px; padding:9px 16px; border:none; border-radius:8px;
    background:{ACCENT}; color:#FFFFFF; font-weight:600;
}}
QPushButton:hover {{ background:#3468BC; }}
QPushButton#ghost {{ background:#EEF0F3; color:#4A4F57; font-weight:normal; }}
QPushButton#ghost:hover {{ background:#E4E7EC; }}
QPushButton#danger {{ background:#FCECEC; color:#C0392B; font-weight:normal; }}
QPushButton#danger:hover {{ background:#F7DCDC; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:#CFD3D9; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:#B9BEC6; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
"""


class _TestWorker(QThread):
    done = Signal(bool, str)

    def run(self):
        ok, msg = client.test()
        self.done.emit(ok, msg)


class SettingsWindow(QWidget):
    changed = Signal()
    scale_changed = Signal(float)
    opacity_changed = Signal(float)
    always_on_top_changed = Signal(bool)
    clothing_changed = Signal(str)
    taskbar_changed = Signal(bool)
    open_role_editor = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("设置")
        self.resize(560, 720)
        self.setStyleSheet(_QSS)
        self._test_worker = None

        tabs = QTabWidget()
        tabs.addTab(self._scroll(self._companion_tab()), "陪伴")
        tabs.addTab(self._scroll(self._chat_tab()), "对话")
        tabs.addTab(self._scroll(self._appearance_tab()), "外观")
        tabs.addTab(self._scroll(self._other_tab()), "其它")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(tabs)

    # ---- 工具 ----
    def _scroll(self, inner):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(inner)
        return sc

    def _page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(18, 14, 18, 20)
        v.setSpacing(10)
        return w, v

    def _toggle(self, key, on_change=None):
        sw = ToggleSwitch(bool(settings.get(key)))
        def h(v):
            settings.set(key, v)
            if on_change:
                on_change(v)
            self.changed.emit()
        sw.toggled.connect(h)
        return sw

    def _slider(self, key, mn, mx, suffix="", scale=1.0, on_change=None):
        cur = settings.get(key)
        val = int(round((cur / scale) if scale != 1.0 else cur))
        sr = SliderRow("", mn, mx, val, suffix)
        def h(v):
            settings.set(key, (v * scale) if scale != 1.0 else v)
            if on_change:
                on_change(v)
            self.changed.emit()
        sr.changed.connect(h)
        return sr

    @staticmethod
    def _open_path(path):
        try:
            os.makedirs(path, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception:
            pass

    # ======== 陪伴 ========
    def _companion_tab(self):
        w, v = self._page()

        # 番茄钟
        v.addWidget(section_title("番茄钟"))
        c = Card()
        c.add_row(Row("启用番茄钟", self._toggle("pomodoro_enabled")))
        c.add_divider()
        c.add_row(self._slider("pomodoro_focus", 1, 120, " 分"))
        r = c._v.itemAt(c._v.count() - 1).widget()
        c.add_divider()
        c.add_row(self._slider("pomodoro_break", 1, 60, " 分"))
        v.addWidget(c)
        # 给番茄钟两条滑块补上标题
        self._relabel_last_sliders(c, ["时长", "休息"])

        # 护眼
        v.addWidget(section_title("护眼"))
        c = Card()
        c.add_row(Row("护眼提醒(20-20-20)", self._toggle("eye_rest_enabled")))
        c.add_divider()
        c.add_row(self._slider("eye_rest_interval", 5, 60, " 分"))
        self._relabel_last_sliders(c, ["间隔"])
        v.addWidget(c)
        v.addWidget(hint_label("到点它会提醒你抬头远眺,陪你一起歇眼睛。"))

        # 提醒
        v.addWidget(section_title("提醒"))
        c = Card()
        c.add_row(Row("夜晚模式(深夜提醒休息)", self._toggle("night_mode")))
        c.add_divider()
        c.add_row(Row("久坐 / 工作陪伴提醒", self._toggle("sedentary_reminder")))
        c.add_divider()
        c.add_row(Row("低电量提醒", self._toggle("watch_battery")))
        c.add_divider()
        c.add_row(Row("稀有彩蛋(偶尔说点意外的话)", self._toggle("rare_enabled")))
        v.addWidget(c)
        v.addWidget(hint_label("稀有彩蛋每天最多出现几次,不会频繁打扰。"))

        # 天气与节日
        v.addWidget(section_title("天气与节日"))
        c = Card()
        c.add_row(Row("天气联动(需要联网)", self._toggle("weather_enabled")))
        v.addWidget(c)
        v.addWidget(hint_label("下雨、下雪会有不同姿势和台词。用免费天气服务按网络位置判断,不需要定位权限。"))
        c = Card()
        c.add_row(Row("节日彩蛋", self._toggle("festival_enabled")))
        c.add_divider()
        bd = QLineEdit(settings.get("birthday"))
        bd.setPlaceholderText("例如 08-27")
        bd.setFixedWidth(110)
        bd.editingFinished.connect(
            lambda: settings.set("birthday", bd.text().strip()))
        c.add_row(Row("生日(MM-DD)", bd))
        v.addWidget(c)

        # 移动
        v.addWidget(section_title("移动"))
        c = Card()
        c.add_row(Row("自动散步", self._toggle("auto_stroll")))
        c.add_divider()
        c.add_row(Row("走到屏幕边缘休息", self._toggle("edge_rest")))
        c.add_divider()
        c.add_row(self._slider("move_speed", 10, 100))
        self._relabel_last_sliders(c, ["移动速度"])
        v.addWidget(c)

        # 系统感知
        v.addWidget(section_title("系统感知"))
        c = Card()
        c.add_row(Row("锁屏 / 合盖时它也去睡", self._toggle("lock_sleep")))
        c.add_divider()
        c.add_row(Row("有程序全屏时自动隐藏", self._toggle("fullscreen_hide")))
        v.addWidget(c)
        v.addWidget(hint_label("看视频、演示、玩游戏时它会自己让开,退出全屏再回来。"))

        # 鼠标互动
        v.addWidget(section_title("鼠标互动"))
        c = Card()
        c.add_row(Row("鼠标靠近时抬头 / 停留时走过去", self._toggle("mouse_interact")))
        v.addWidget(c)

        # 发呆
        v.addWidget(section_title("发呆"))
        c = Card()
        c.add_row(Row("长时间无操作后坐下", self._toggle("idle_sit")))
        c.add_divider()
        c.add_row(self._slider("idle_wait_min", 1, 30, " 分"))
        self._relabel_last_sliders(c, ["等待时间"])
        v.addWidget(c)

        # 主动搭话
        v.addWidget(section_title("主动搭话"))
        c = Card()
        seg = Segmented(
            [("none", "不主动说"), ("few", "很少"), ("normal", "正常"), ("more", "较多")],
            settings.get("chatter_freq"))
        seg.changed.connect(lambda k: (settings.set("chatter_freq", k), self.changed.emit()))
        c.add_row(Row("说话频率", seg))
        v.addWidget(c)
        v.addWidget(hint_label("除了点击回应之外,它偶尔会自己说一句。同一轮里不会重复同一句话。"))

        # 安静时段
        v.addWidget(section_title("安静时段"))
        c = Card()
        c.add_row(Row("在指定时段内不主动说话", self._toggle("quiet_enabled")))
        c.add_divider()
        c.add_row(self._slider("quiet_start", 0, 23, " 点"))
        self._relabel_last_sliders(c, ["从"])
        c.add_divider()
        c.add_row(self._slider("quiet_end", 0, 23, " 点"))
        self._relabel_last_sliders(c, ["到"])
        v.addWidget(c)

        # 感知与心情
        v.addWidget(section_title("感知与心情"))
        c = Card()
        c.add_row(Row("感知你在用什么软件并做出反应", self._toggle("watch_activity")))
        v.addWidget(c)
        v.addWidget(hint_label("写代码、听音乐、看文档时反应不同。只读取软件名称,不读取任何窗口内容。"))
        c = Card()
        c.add_row(Row("心情系统", self._toggle("mood_enabled")))
        c.add_divider()
        c.add_row(Row("启动时按时段问候", self._toggle("greet_on_start")))
        v.addWidget(c)
        v.addWidget(hint_label("心情会随时间、天气、你的互动频率变化,影响它多话还是安静、爱不爱走动。"))

        v.addStretch(1)
        return w

    def _relabel_last_sliders(self, card, titles):
        """给刚加进卡片的 SliderRow 补标题(SliderRow 的标题在第0个 widget)。"""
        rows = [card._v.itemAt(i).widget() for i in range(card._v.count())]
        sliders = [r for r in rows if isinstance(r, SliderRow)]
        for sr, t in zip(sliders[-len(titles):], titles):
            lbl = sr.layout().itemAt(0).widget()
            if isinstance(lbl, QLabel):
                lbl.setText(t)

    # ======== 对话 ========
    def _chat_tab(self):
        w, v = self._page()

        c = Card()
        form = QFormLayout()
        form.setContentsMargins(0, 8, 0, 8)
        form.setSpacing(10)

        self._enabled = ToggleSwitch(bool(settings.get("ai_enabled")))
        self._enabled.toggled.connect(lambda b: (settings.set("ai_enabled", b), self.changed.emit()))
        form.addRow("启用 AI 对话", self._enabled)

        self._provider = QComboBox()
        for p in PROVIDERS:
            self._provider.addItem(p.name, p.id)
        idx = next((i for i, p in enumerate(PROVIDERS)
                    if p.id == settings.get("ai_provider")), 0)
        self._provider.setCurrentIndex(idx)
        self._provider.currentIndexChanged.connect(self._on_provider)
        form.addRow("服务商", self._provider)

        self._note = hint_label("")
        form.addRow("", self._note)

        self._key = QLineEdit(settings.get("ai_key"))
        self._key.setEchoMode(QLineEdit.Password)
        self._key.setPlaceholderText("在服务商后台申请")
        self._key.editingFinished.connect(self._save_ai)
        form.addRow("密钥(API Key)", self._key)

        self._model = QLineEdit(settings.get("ai_model"))
        self._model.setPlaceholderText("留空用默认模型")
        self._model.editingFinished.connect(self._save_ai)
        form.addRow("模型(可选)", self._model)

        self._host = QLineEdit(settings.get("ai_host"))
        self._host.setPlaceholderText("留空用默认地址")
        self._host.editingFinished.connect(self._save_ai)
        form.addRow("接口地址(可选)", self._host)
        c._v.addLayout(form)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._on_test)
        test_row.addWidget(self._test_btn)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        self._test_result.setStyleSheet("background:transparent;font-size:13px;")
        test_row.addWidget(self._test_result, 1)
        c._v.addLayout(test_row)
        v.addWidget(c)

        # 它是谁
        v.addWidget(section_title("它是谁"))
        c = Card()
        r = QHBoxLayout()
        left = QVBoxLayout()
        t = QLabel("角色设定")
        t.setStyleSheet("font-size:15px;font-weight:bold;background:transparent;")
        left.addWidget(t)
        left.addWidget(hint_label("完全由你决定 —— 程序不写任何人设"))
        r.addLayout(left, 1)
        openbtn = QPushButton("打开角色设定")
        openbtn.clicked.connect(self.open_role_editor.emit)
        r.addWidget(openbtn, 0, Qt.AlignVCenter)
        c._v.addLayout(r)
        v.addWidget(c)

        # 高级
        v.addWidget(section_title("高级"))
        c = Card()
        c.add_row(self._slider("ai_memory_turns", 2, 40, " 轮"))
        self._relabel_last_sliders(c, ["记住最近"])
        c.add_divider()
        c.add_row(self._slider("ai_max_tokens", 100, 2000))
        self._relabel_last_sliders(c, ["回复长度上限"])
        c.add_divider()
        self._scene_lines = ToggleSwitch(bool(settings.get("ai_scene_lines")))
        self._scene_lines.toggled.connect(
            lambda b: (settings.set("ai_scene_lines", b), self.changed.emit()))
        c.add_row(Row("点击/问候台词由 AI 按人设生成", self._scene_lines))
        c.add_divider()
        clr = QPushButton("清空聊天记录"); clr.setObjectName("ghost")
        clr.clicked.connect(self._clear_chat)
        c._v.addWidget(clr)
        c._v.addSpacing(6)
        v.addWidget(c)

        v.addWidget(section_title("说句实话"))
        v.addWidget(hint_label(
            "小模型演不住人物,免费的那些聊几轮就会滑回助手腔,这不是提示词能补救的。\n"
            "在意角色感的话:国内用 deepseek-chat 或 glm-4-plus,国外用 Claude。"))

        self._on_provider()
        v.addStretch(1)
        return w

    def _on_provider(self):
        p = find_provider(self._provider.currentData())
        self._note.setText(f"{p.note}\n后台:{p.console}" if p.console else p.note)
        self._save_ai()

    def _save_ai(self):
        settings.set("ai_enabled", self._enabled.isChecked())
        settings.set("ai_provider", self._provider.currentData())
        settings.set("ai_key", self._key.text().strip())
        settings.set("ai_model", self._model.text().strip())
        settings.set("ai_host", self._host.text().strip())
        self.changed.emit()

    def _on_test(self):
        if self._test_worker is not None:
            return
        self._save_ai()
        self._test_btn.setEnabled(False)
        self._test_result.setText("测试中…")
        self._test_worker = _TestWorker()
        self._test_worker.done.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, ok, msg):
        self._test_result.setStyleSheet(
            f"background:transparent;font-size:13px;color:{'#3a8f4f' if ok else '#C0392B'};")
        self._test_result.setText(msg)
        self._test_btn.setEnabled(True)
        self._test_worker = None

    def _clear_chat(self):
        from conversation import conversation
        conversation.clear()
        self._test_result.setText("聊天记录已清空")

    # ======== 外观 ========
    def _appearance_tab(self):
        w, v = self._page()

        v.addWidget(section_title("服装"))
        c = Card()
        seg = Segmented(
            [("hoodie", "卫衣"), ("polo", "Polo"), ("jacket", "外套")],
            settings.get("clothing"))
        seg.changed.connect(self._on_clothing)
        c.add_row(Row("当前服装", seg))
        v.addWidget(c)
        v.addWidget(hint_label("注:目前 Polo 和外套只有站立单图,走路/看书等动作仍用默认卫衣。"))

        v.addWidget(section_title("显示"))
        c = Card()
        sr = self._slider("pet_scale", 30, 250, "%", scale=0.01,
                          on_change=lambda v: self.scale_changed.emit(v / 100.0))
        c.add_row(sr)
        self._relabel_last_sliders(c, ["大小"])
        c.add_divider()
        sr2 = self._slider("opacity", 30, 100, "%", scale=0.01,
                           on_change=lambda v: self.opacity_changed.emit(v / 100.0))
        c.add_row(sr2)
        self._relabel_last_sliders(c, ["透明度"])
        v.addWidget(c)

        v.addStretch(1)
        return w

    def _on_clothing(self, key):
        settings.set("clothing", key)
        self.clothing_changed.emit(key)
        self.changed.emit()

    # ======== 其它 ========
    def _other_tab(self):
        w, v = self._page()

        c = Card()
        c.add_row(Row("始终置顶", self._toggle(
            "always_on_top", on_change=lambda b: self.always_on_top_changed.emit(b))))
        c.add_divider()
        c.add_row(Row("开机自动启动", self._toggle("autostart", on_change=self._apply_autostart)))
        c.add_divider()
        c.add_row(Row("点击时说话", self._toggle("click_to_talk")))
        c.add_divider()
        c.add_row(Row("在任务栏显示图标", self._toggle(
            "show_in_taskbar", on_change=lambda b: self.taskbar_changed.emit(b))))
        v.addWidget(c)

        v.addWidget(section_title("素材与台词"))
        c = Card()
        b1 = QPushButton("还原成内置台词"); b1.setObjectName("ghost")
        b1.clicked.connect(self._reset_lines)
        c._v.addWidget(b1); c._v.addSpacing(6)
        c.add_divider()
        b2 = QPushButton("打开数据文件夹"); b2.setObjectName("ghost")
        b2.clicked.connect(lambda: self._open_path(support_dir()))
        c._v.addWidget(b2); c._v.addSpacing(6)
        b3 = QPushButton("打开角色图片文件夹"); b3.setObjectName("ghost")
        b3.clicked.connect(self._open_custom_images)
        c._v.addWidget(b3); c._v.addSpacing(6)
        v.addWidget(c)
        v.addWidget(hint_label(
            "把同名 png 放进「角色图片文件夹」就能替换对应动作的图,重启桌宠生效。"))

        # 名字
        v.addWidget(section_title("名字"))
        c = Card()
        from role_profile import role
        self._name_it = QLineEdit(role.get("name"))
        self._name_it.editingFinished.connect(
            lambda: role.set("name", self._name_it.text()))
        c.add_row(Row("它叫什么", self._name_it))
        c.add_divider()
        self._name_you = QLineEdit(settings.get("user_name"))
        self._name_you.editingFinished.connect(
            lambda: settings.set("user_name", self._name_you.text()))
        c.add_row(Row("你叫什么", self._name_you))
        c.add_divider()
        self._call_you = QLineEdit(role.user_description)
        self._call_you.setPlaceholderText("留空就用上面那个")
        self._call_you.editingFinished.connect(
            lambda: setattr(role, "user_description", self._call_you.text()))
        c.add_row(Row("它怎么称呼你", self._call_you))
        v.addWidget(c)

        # 最近的问题
        v.addWidget(section_title("最近的问题"))
        c = Card()
        c.add_row(Row("拿不到数据时含糊提一句", self._toggle("failure_hint")))
        v.addWidget(c)
        from failure_log import failure_log
        self._problems = QTextEdit()
        self._problems.setReadOnly(True)
        self._problems.setFixedHeight(110)
        self._problems.setPlainText(failure_log.summary())
        v.addWidget(self._problems)
        rf = QPushButton("刷新"); rf.setObjectName("ghost")
        rf.clicked.connect(lambda: self._problems.setPlainText(failure_log.summary()))
        v.addWidget(rf)

        # 清除个人信息
        v.addWidget(section_title("清除个人信息"))
        v.addWidget(hint_label(
            "会抹掉:名字、生日、提醒、陪伴记录、角色设定、聊天记录这些。不会删你换过的图片。"))
        wipe = QPushButton("清除个人信息"); wipe.setObjectName("danger")
        wipe.clicked.connect(self._wipe)
        v.addWidget(wipe)

        v.addStretch(1)
        return w

    def _apply_autostart(self, on):
        try:
            import autostart
            autostart.set_enabled(bool(on))
        except Exception:
            pass

    def _reset_lines(self):
        from role_lines import role_lines
        role_lines.regenerate()

    def _open_custom_images(self):
        d = os.path.join(support_dir(), "PetImages")
        self._open_path(d)

    def _wipe(self):
        box = QMessageBox(self)
        box.setWindowTitle("确认")
        box.setText("确定清除个人信息吗?此操作不可撤销。")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if box.exec() != QMessageBox.Yes:
            return
        for name in ["role.json", "chat.json", "companion.json", "reminders.json",
                     "role_lines.json", "events.json", "角色设定.txt", "角色台词.txt"]:
            try:
                os.remove(os.path.join(support_dir(), name))
            except Exception:
                pass
        for key in ["birthday", "user_name"]:
            settings.set(key, "")
        self._problems.setPlainText("已清除。部分改动重启后完全生效。")
