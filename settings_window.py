"""设置窗口。两个标签页:对话(AI 配置) + 角色(人设)。"""
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

        root = QVBoxLayout(self)
        root.addWidget(tabs)

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
