"""设置窗口。两个标签页:对话(AI 配置) + 角色(人设)。"""
import os
import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton, QTextEdit,
    QDoubleSpinBox, QSpinBox, QScrollArea, QSlider,
)

from settings import settings
from ai_client import client, PROVIDERS, find_provider
from role_profile import role, FIELDS
from role_lines import role_lines


class _TestWorker(QThread):
    done = Signal(bool, str)

    def run(self):
        ok, msg = client.test()
        self.done.emit(ok, msg)


class _PreviewWorker(QThread):
    done = Signal(str)

    def __init__(self, text):
        super().__init__()
        self._text = text

    def run(self):
        import ai_service
        reply = ai_service.preview(self._text)
        self.done.emit(reply)


class SettingsWindow(QWidget):
    changed = Signal()          # 设置变动时通知主程序刷新状态
    scale_changed = Signal(float)   # 角色大小变动时,让主程序实时缩放

    def __init__(self):
        super().__init__()
        self.setWindowTitle("设置")
        self.resize(480, 640)
        self._test_worker = None

        tabs = QTabWidget()
        tabs.addTab(self._build_ai_tab(), "对话")
        tabs.addTab(self._build_role_tab(), "角色")
        tabs.addTab(self._build_appearance_tab(), "外观")
        tabs.addTab(self._build_problems_tab(), "最近的问题")

        root = QVBoxLayout(self)
        root.addWidget(tabs)

    # ---------- 最近的问题 ----------
    def _build_problems_tab(self):
        from failure_log import failure_log
        w = QWidget()
        v = QVBoxLayout(w)
        tip = QLabel("这里记录最近哪些功能没取到数据(比如天气拉取失败、AI 报错)。"
                     "功能恢复后会自动消失。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#888; font-size:12px;")
        v.addWidget(tip)
        self._problems = QTextEdit()
        self._problems.setReadOnly(True)
        v.addWidget(self._problems, 1)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(
            lambda: self._problems.setPlainText(failure_log.summary()))
        v.addWidget(refresh)
        self._problems.setPlainText(failure_log.summary())
        return w

    # ---------- 外观标签页 ----------
    def _build_appearance_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        lbl = QLabel("角色大小")
        lbl.setStyleSheet("font-weight:bold;")
        v.addWidget(lbl)

        self._scale_value = QLabel()
        v.addWidget(self._scale_value)

        self._scale_slider = QSlider(Qt.Horizontal)
        self._scale_slider.setMinimum(30)    # 0.30 倍
        self._scale_slider.setMaximum(250)   # 2.50 倍
        cur = int(round(float(settings.get("pet_scale")) * 100))
        self._scale_slider.setValue(max(30, min(250, cur)))
        self._scale_slider.valueChanged.connect(self._on_scale)
        v.addWidget(self._scale_slider)

        hint = QLabel("拖动滑块实时调整。太大就往左拖。")
        hint.setStyleSheet("color:#999; font-size:11px;")
        v.addWidget(hint)

        v.addSpacing(16)
        behave = QLabel("行为")
        behave.setStyleSheet("font-weight:bold;")
        v.addWidget(behave)

        self._watch_activity = QCheckBox("根据你在用什么软件切换姿势/台词(听歌、打字、看网页)")
        self._watch_activity.setChecked(bool(settings.get("watch_activity")))
        self._watch_activity.stateChanged.connect(
            lambda: settings.set("watch_activity", self._watch_activity.isChecked()))
        v.addWidget(self._watch_activity)

        self._watch_battery = QCheckBox("电脑快没电时提醒")
        self._watch_battery.setChecked(bool(settings.get("watch_battery")))
        self._watch_battery.stateChanged.connect(
            lambda: settings.set("watch_battery", self._watch_battery.isChecked()))
        v.addWidget(self._watch_battery)

        self._weather = QCheckBox("获取天气,下雨下雪会有反应")
        self._weather.setChecked(bool(settings.get("weather_enabled")))
        self._weather.stateChanged.connect(
            lambda: settings.set("weather_enabled", self._weather.isChecked()))
        v.addWidget(self._weather)

        bd_row = QHBoxLayout()
        bd_row.addWidget(QLabel("你的生日(MM-DD,到日子它会说生日快乐)"))
        self._birthday = QLineEdit(settings.get("birthday"))
        self._birthday.setPlaceholderText("例如 08-15")
        self._birthday.setFixedWidth(90)
        self._birthday.editingFinished.connect(
            lambda: settings.set("birthday", self._birthday.text().strip()))
        bd_row.addWidget(self._birthday)
        v.addLayout(bd_row)

        privacy = QLabel("这两项只在你本机读取,不上传任何信息。")
        privacy.setWordWrap(True)
        privacy.setStyleSheet("color:#999; font-size:11px;")
        v.addWidget(privacy)

        v.addStretch(1)
        self._update_scale_label()
        return w

    def _on_scale(self, val):
        scale = val / 100.0
        settings.set("pet_scale", scale)
        self._update_scale_label()
        self.scale_changed.emit(scale)

    def _update_scale_label(self):
        s = float(settings.get("pet_scale"))
        self._scale_value.setText(f"当前:{s:.2f} 倍")

    # ---------- 对话标签页 ----------
    def _build_ai_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self._enabled = QCheckBox("启用 AI 对话")
        self._enabled.setChecked(bool(settings.get("ai_enabled")))
        self._enabled.stateChanged.connect(self._save_ai)
        form.addRow(self._enabled)

        self._provider = QComboBox()
        for p in PROVIDERS:
            self._provider.addItem(p.name, p.id)
        idx = next((i for i, p in enumerate(PROVIDERS)
                    if p.id == settings.get("ai_provider")), 0)
        self._provider.setCurrentIndex(idx)
        self._provider.currentIndexChanged.connect(self._on_provider)
        form.addRow("服务商", self._provider)

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setStyleSheet("color:#888; font-size:12px;")
        form.addRow("", self._note)

        self._key = QLineEdit(settings.get("ai_key"))
        self._key.setEchoMode(QLineEdit.Password)
        self._key.setPlaceholderText("在服务商后台申请")
        self._key.editingFinished.connect(self._save_ai)
        form.addRow("API Key", self._key)

        self._model = QLineEdit(settings.get("ai_model"))
        self._model.setPlaceholderText("留空用默认模型")
        self._model.editingFinished.connect(self._save_ai)
        form.addRow("模型(可选)", self._model)

        self._host = QLineEdit(settings.get("ai_host"))
        self._host.setPlaceholderText("留空用默认地址")
        self._host.editingFinished.connect(self._save_ai)
        form.addRow("接口地址(可选)", self._host)

        self._temp = QDoubleSpinBox()
        self._temp.setRange(0.0, 2.0)
        self._temp.setSingleStep(0.1)
        self._temp.setValue(float(settings.get("ai_temperature")))
        self._temp.valueChanged.connect(self._save_ai)
        form.addRow("随机度 temperature", self._temp)

        self._maxtok = QSpinBox()
        self._maxtok.setRange(64, 4096)
        self._maxtok.setValue(int(settings.get("ai_max_tokens")))
        self._maxtok.valueChanged.connect(self._save_ai)
        form.addRow("单次最长回复", self._maxtok)

        self._framing = QCheckBox("附加收尾提示(让它别跳戏、别写旁白)")
        self._framing.setChecked(bool(settings.get("ai_add_framing_note")))
        self._framing.stateChanged.connect(self._save_ai)
        form.addRow(self._framing)

        self._scene_lines = QCheckBox("点击/问候等台词由 AI 按人设生成")
        self._scene_lines.setChecked(bool(settings.get("ai_scene_lines")))
        self._scene_lines.stateChanged.connect(self._save_ai)
        form.addRow(self._scene_lines)

        regen_row = QHBoxLayout()
        self._regen_btn = QPushButton("重新生成台词")
        self._regen_btn.clicked.connect(self._on_regen)
        regen_row.addWidget(self._regen_btn)
        self._regen_status = QLabel(role_lines.status_text())
        self._regen_status.setStyleSheet("color:#888; font-size:12px;")
        regen_row.addWidget(self._regen_status, 1)
        form.addRow(regen_row)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._on_test)
        test_row.addWidget(self._test_btn)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        test_row.addWidget(self._test_result, 1)
        form.addRow(test_row)

        self._on_provider()  # 初始化提示文字
        return w

    def _on_provider(self):
        pid = self._provider.currentData()
        p = find_provider(pid)
        self._note.setText(f"{p.note}\n后台:{p.console}" if p.console else p.note)
        self._save_ai()

    def _save_ai(self):
        settings.set("ai_enabled", self._enabled.isChecked())
        settings.set("ai_provider", self._provider.currentData())
        settings.set("ai_key", self._key.text().strip())
        settings.set("ai_model", self._model.text().strip())
        settings.set("ai_host", self._host.text().strip())
        settings.set("ai_temperature", self._temp.value())
        settings.set("ai_max_tokens", self._maxtok.value())
        settings.set("ai_add_framing_note", self._framing.isChecked())
        settings.set("ai_scene_lines", self._scene_lines.isChecked())
        self.changed.emit()

    def _on_regen(self):
        role_lines.regenerate()
        self._regen_status.setText("已触发,正在后台按你的设定生成…")

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
            "color:#3a3;" if ok else "color:#c33;")
        self._test_result.setText(msg)
        self._test_btn.setEnabled(True)
        self._test_worker = None

    # ---------- 角色标签页 ----------
    def _build_role_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        v = QVBoxLayout(inner)

        tip = QLabel("这些内容会**原样**发给模型,程序不额外加任何性格。填得越具体越像。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#888; font-size:12px;")
        v.addWidget(tip)

        self._role_edits = {}
        for f in FIELDS:
            lbl = QLabel(f.title)
            lbl.setStyleSheet("font-weight:bold;")
            v.addWidget(lbl)
            hint = QLabel(f.hint)
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#999; font-size:11px;")
            v.addWidget(hint)
            if f.multiline:
                e = QTextEdit(role.get(f.key))
                e.setFixedHeight(70)
            else:
                e = QLineEdit(role.get(f.key))
            self._role_edits[f.key] = e
            v.addWidget(e)

        # 和你说话的人
        lbl = QLabel("和你说话的人")
        lbl.setStyleSheet("font-weight:bold;")
        v.addWidget(lbl)
        self._user_desc = QLineEdit(role.user_description)
        self._user_desc.setPlaceholderText("你是谁、它该怎么称呼你")
        v.addWidget(self._user_desc)

        save_btn = QPushButton("保存角色设定")
        save_btn.clicked.connect(self._save_role)
        v.addWidget(save_btn)

        self._role_saved = QLabel("")
        self._role_saved.setStyleSheet("color:#3a3; font-size:12px;")
        v.addWidget(self._role_saved)

        # 大段编辑:导出 txt / 读回
        v.addSpacing(8)
        edit_lbl = QLabel("嫌输入框小?可以导出成文本文件大段编辑,改完读回:")
        edit_lbl.setWordWrap(True)
        edit_lbl.setStyleSheet("color:#888; font-size:12px;")
        v.addWidget(edit_lbl)
        er = QHBoxLayout()
        exp_btn = QPushButton("导出为文本编辑")
        exp_btn.clicked.connect(self._export_role_text)
        er.addWidget(exp_btn)
        imp_btn = QPushButton("从文件读回")
        imp_btn.clicked.connect(self._import_role_text)
        er.addWidget(imp_btn)
        v.addLayout(er)

        # 试一下台词
        v.addSpacing(12)
        pv_lbl = QLabel("试一下它会怎么回(不进聊天记录,方便反复调设定):")
        pv_lbl.setWordWrap(True)
        pv_lbl.setStyleSheet("font-weight:bold;")
        v.addWidget(pv_lbl)
        self._preview_input = QLineEdit()
        self._preview_input.setPlaceholderText("输入一句话试试,回车")
        self._preview_input.returnPressed.connect(self._on_preview)
        v.addWidget(self._preview_input)
        self._preview_out = QLabel("")
        self._preview_out.setWordWrap(True)
        self._preview_out.setStyleSheet("color:#555; background:#f4f4f4; padding:8px; border-radius:6px;")
        v.addWidget(self._preview_out)

        # 编辑场景台词
        v.addSpacing(12)
        sl_lbl = QLabel("场景台词(点击/问候等)导出编辑、读回:")
        sl_lbl.setWordWrap(True)
        sl_lbl.setStyleSheet("color:#888; font-size:12px;")
        v.addWidget(sl_lbl)
        sr = QHBoxLayout()
        sl_exp = QPushButton("导出台词编辑")
        sl_exp.clicked.connect(self._export_lines)
        sr.addWidget(sl_exp)
        sl_imp = QPushButton("读回台词")
        sl_imp.clicked.connect(self._import_lines)
        sr.addWidget(sl_imp)
        v.addLayout(sr)
        self._lines_status = QLabel("")
        self._lines_status.setStyleSheet("color:#888; font-size:12px;")
        v.addWidget(self._lines_status)

        v.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _save_role(self):
        for key, edit in self._role_edits.items():
            if isinstance(edit, QTextEdit):
                role.set(key, edit.toPlainText())
            else:
                role.set(key, edit.text())
        role.user_description = self._user_desc.text()
        role_lines.regenerate()   # 人设变了,台词按新设定重生成
        self._role_saved.setText("已保存(台词将按新设定重新生成)")
        self.changed.emit()

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)   # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception:
            pass

    def _export_role_text(self):
        p = role.export_text()
        if p:
            self._open_file(p)
            self._role_saved.setText("已导出并打开,改完保存,再点「从文件读回」")

    def _import_role_text(self):
        if role.import_text():
            # 刷新界面上的输入框
            for key, edit in self._role_edits.items():
                if isinstance(edit, QTextEdit):
                    edit.setPlainText(role.get(key))
                else:
                    edit.setText(role.get(key))
            self._user_desc.setText(role.user_description)
            role_lines.regenerate()
            self._role_saved.setText("已读回(台词将按新设定重新生成)")
        else:
            self._role_saved.setText("没读到内容,先点「导出为文本编辑」")

    def _on_preview(self):
        text = self._preview_input.text().strip()
        if not text:
            return
        self._preview_out.setText("……")
        self._preview_worker = _PreviewWorker(text)
        self._preview_worker.done.connect(self._preview_out.setText)
        self._preview_worker.start()

    def _export_lines(self):
        p = role_lines.export_for_editing()
        if p:
            self._open_file(p)
            self._lines_status.setText("已导出并打开,改完保存,再点「读回台词」")
        else:
            self._lines_status.setText("还没有生成的台词。先在「对话」页点「重新生成台词」")

    def _import_lines(self):
        if role_lines.import_from_editing():
            self._lines_status.setText("已读回你改的台词")
        else:
            self._lines_status.setText("没读到内容,先点「导出台词编辑」")
