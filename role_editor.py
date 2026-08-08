"""角色设定窗口。人设栏目 + 试一下台词 + 导出/读回 + 台词编辑。

样式统一:白底、微软雅黑、蓝色主色、圆角卡片。
"""
import os
import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QScrollArea,
)

from role_profile import role, FIELDS
from role_lines import role_lines
from ui_widgets import ACCENT, FONT, Card, section_title, hint_label

_QSS = f"""
QWidget {{ background:#F6F8FA; font-family:{FONT}; color:#2B2F36; }}
QLineEdit, QTextEdit {{
    background:#FFFFFF; border:1px solid #D8DEE8; border-radius:8px;
    padding:8px; font-size:14px;
}}
QLineEdit:focus, QTextEdit:focus {{ border-color:{ACCENT}; }}
QPushButton {{
    font-size:14px; padding:9px 16px; border:none; border-radius:8px;
    background:{ACCENT}; color:#FFFFFF; font-weight:bold;
}}
QPushButton:hover {{ background:#3468BC; }}
QPushButton#ghost {{ background:#EEF1F5; color:#555; font-weight:normal; }}
QPushButton#ghost:hover {{ background:#E2E7EE; }}
"""


class _PreviewWorker(QThread):
    done = Signal(str)

    def __init__(self, text):
        super().__init__()
        self._text = text

    def run(self):
        import ai_service
        self.done.emit(ai_service.preview(self._text))


class RoleEditorWindow(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("角色设定")
        self.resize(520, 680)
        self.setStyleSheet(_QSS)
        self._preview_worker = None

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#F6F8FA;}")
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(12)

        v.addWidget(hint_label(
            "这些内容会原样发给模型,程序不额外加任何性格。填得越具体越像。"))

        # 人设栏目
        card = Card()
        self._edits = {}
        for i, f in enumerate(FIELDS):
            title = QLabel(f.title)
            title.setStyleSheet("font-size:15px;font-weight:bold;background:transparent;")
            card._v.addWidget(title)
            card._v.addWidget(hint_label(f.hint))
            if f.multiline:
                e = QTextEdit(role.get(f.key))
                e.setFixedHeight(70)
            else:
                e = QLineEdit(role.get(f.key))
            self._edits[f.key] = e
            card._v.addWidget(e)
            card._v.addSpacing(8)
        v.addWidget(card)

        # 名字/称呼
        v.addWidget(section_title("和你说话的人"))
        card2 = Card()
        self._user_desc = QLineEdit(role.user_description)
        self._user_desc.setPlaceholderText("你是谁、它该怎么称呼你")
        card2._v.addWidget(self._user_desc)
        v.addWidget(card2)

        save = QPushButton("保存角色设定")
        save.clicked.connect(self._save)
        v.addWidget(save)
        self._saved = QLabel("")
        self._saved.setStyleSheet("color:#3a8f4f;font-size:12px;background:transparent;")
        v.addWidget(self._saved)

        # 大段编辑
        v.addWidget(section_title("大段编辑"))
        v.addWidget(hint_label("嫌输入框小?导出成文本文件慢慢改,改完读回。"))
        er = QHBoxLayout()
        b1 = QPushButton("导出为文本编辑"); b1.setObjectName("ghost")
        b1.clicked.connect(self._export_role)
        er.addWidget(b1)
        b2 = QPushButton("从文件读回"); b2.setObjectName("ghost")
        b2.clicked.connect(self._import_role)
        er.addWidget(b2)
        v.addLayout(er)

        # 试台词
        v.addWidget(section_title("试一下它会怎么回"))
        v.addWidget(hint_label("输入一句试试,不进聊天记录,方便反复调设定。"))
        self._pv_in = QLineEdit()
        self._pv_in.setPlaceholderText("输入一句话,回车")
        self._pv_in.returnPressed.connect(self._preview)
        v.addWidget(self._pv_in)
        self._pv_out = QLabel("")
        self._pv_out.setWordWrap(True)
        self._pv_out.setStyleSheet(
            "background:#FFFFFF;border:1px solid #ECEFF3;border-radius:8px;"
            "padding:10px;color:#444;font-size:14px;")
        v.addWidget(self._pv_out)

        # 台词编辑
        v.addWidget(section_title("场景台词"))
        v.addWidget(hint_label("点击/问候等台词,可导出编辑再读回;也能一键按人设重新生成。"))
        sr = QHBoxLayout()
        b3 = QPushButton("重新生成台词"); b3.setObjectName("ghost")
        b3.clicked.connect(self._regen)
        sr.addWidget(b3)
        b4 = QPushButton("导出台词编辑"); b4.setObjectName("ghost")
        b4.clicked.connect(self._export_lines)
        sr.addWidget(b4)
        b5 = QPushButton("读回台词"); b5.setObjectName("ghost")
        b5.clicked.connect(self._import_lines)
        sr.addWidget(b5)
        v.addLayout(sr)
        self._lines_status = QLabel(role_lines.status_text())
        self._lines_status.setStyleSheet("color:#9AA1AB;font-size:12px;background:transparent;")
        v.addWidget(self._lines_status)

        v.addStretch(1)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ---- 逻辑 ----
    def _save(self):
        for k, e in self._edits.items():
            role.set(k, e.toPlainText() if isinstance(e, QTextEdit) else e.text())
        role.user_description = self._user_desc.text()
        role_lines.regenerate()
        self._saved.setText("已保存(台词将按新设定重新生成)")
        self.changed.emit()

    @staticmethod
    def _open(path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)   # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception:
            pass

    def _export_role(self):
        p = role.export_text()
        if p:
            self._open(p)
            self._saved.setText("已导出并打开,改完保存,再点「从文件读回」")

    def _import_role(self):
        if role.import_text():
            for k, e in self._edits.items():
                if isinstance(e, QTextEdit):
                    e.setPlainText(role.get(k))
                else:
                    e.setText(role.get(k))
            self._user_desc.setText(role.user_description)
            role_lines.regenerate()
            self._saved.setText("已读回")
            self.changed.emit()
        else:
            self._saved.setText("没读到内容,先点「导出为文本编辑」")

    def _preview(self):
        t = self._pv_in.text().strip()
        if not t:
            return
        self._pv_out.setText("……")
        self._preview_worker = _PreviewWorker(t)
        self._preview_worker.done.connect(self._pv_out.setText)
        self._preview_worker.start()

    def _regen(self):
        role_lines.regenerate()
        self._lines_status.setText("已触发,正在后台按你的设定生成…")

    def _export_lines(self):
        p = role_lines.export_for_editing()
        if p:
            self._open(p)
            self._lines_status.setText("已导出并打开,改完保存,再点「读回台词」")
        else:
            self._lines_status.setText("还没有生成的台词,先点「重新生成台词」")

    def _import_lines(self):
        if role_lines.import_from_editing():
            self._lines_status.setText("已读回你改的台词")
        else:
            self._lines_status.setText("没读到内容,先点「导出台词编辑」")
