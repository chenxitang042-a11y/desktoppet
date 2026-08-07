"""角色设定。移植自 Mac 版 RoleProfile.swift。

**核心原则:程序不写人设。**
只做两件事:存用户填的内容、把它原样拼成系统提示词。
不加性格、不加语气要求、不加"你是 AI 要否认"这类东西 ——
那些用户想要就自己写进栏目里。
"""
import json

from paths import support_path
from settings import settings

class Field:
    def __init__(self, key, title, hint, multiline):
        self.key = key
        self.title = title
        self.hint = hint
        self.multiline = multiline


# 顺序就是界面上的顺序,和 Mac 版一致
FIELDS = [
    Field("name", "名字", "它叫什么", False),
    Field("relation", "和你的关系", "比如:朋友、同事、家人。写得具体点更好", False),
    Field("identity", "身份", "年龄段、做什么的、现在什么状态", False),
    Field("personality", "性格",
          "别只写「温柔」这种词。写它在具体情况下会怎么样,"
          "比如「被夸会岔开话题」「不喜欢别人替它做决定」", True),
    Field("speech", "说话方式",
          "最重要的一栏。话多还是话少、句子长短、常用词、口头禅、"
          "怎么表达关心、什么时候会问你问题、什么时候会沉默", True),
    Field("background", "经历背景",
          "它的过去、你们怎么认识的、有什么共同经历", True),
    Field("taboo", "绝不会做", "它绝不会说的话、绝不会有的语气", True),
    Field("extra", "其它", "还想补充的任何东西", True),
]


class RoleProfile:
    def __init__(self):
        self._path = support_path("role.json")
        self._values = {}
        self.load()

    def get(self, key):
        return self._values.get(key, "")

    def set(self, key, value):
        self._values[key] = value
        self.save()

    @property
    def user_description(self):
        return self._values.get("userDesc", "")

    @user_description.setter
    def user_description(self, value):
        self._values["userDesc"] = value
        self.save()

    @property
    def is_empty(self):
        return all(not str(v).strip() for v in self._values.values())

    def filled_count(self):
        n = sum(1 for f in FIELDS if self.get(f.key).strip())
        return n, len(FIELDS)

    @property
    def hint(self):
        n, _ = self.filled_count()
        if n == 0:
            return "还没填 —— 填了它才知道自己是谁"
        if n <= 2:
            return "填得有点少,模型只能靠套路补,演不太像"
        if n <= 4:
            return "还行。补上「说话方式」效果会明显好很多"
        return "挺完整"

    def build_system_prompt(self):
        """拼出发给模型的系统提示词。只包含用户填的内容。"""
        parts = []
        for f in FIELDS:
            v = self.get(f.key).strip()
            if v:
                parts.append(f"【{f.title}】\n{v}")
        if not parts:
            return ""

        body = "\n\n".join(parts)

        user = self.user_description.strip()
        if user:
            body += f"\n\n【和你说话的人】\n{user}"

        # 唯一由程序添加的内容,只讲"怎么用上面的设定",不规定性格。
        # 用户不满意可以在设置里关掉。
        if settings.get("ai_add_framing_note"):
            body += (
                "\n\n\n———\n"
                "以上就是你。用这个身份说话,不要跳出来解释自己在扮演。\n"
                "回复直接说话就行,不要写旁白或动作描写。"
            )
        return body

    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._values, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._values = json.load(f)
        except Exception:
            self._values = {}

    # ---- 导出成 txt 大段编辑 / 读回(移植自 Mac 版)----
    @property
    def text_file_path(self):
        return support_path("角色设定.txt")

    def export_text(self):
        lines = [
            "# 角色设定",
            "#",
            "# 每一栏的内容会**原样**发给模型,程序不额外加任何性格描述。",
            "# 改完保存,回窗口里点「从文件读回」。",
            "#",
            "# 格式:【栏目名】下面写内容,空行分隔。不要改栏目名。",
            "",
        ]
        for f in FIELDS:
            lines.append(f"【{f.title}】")
            v = self.get(f.key).strip()
            lines.append(v if v else f"# {f.hint.splitlines()[0]}")
            lines.append("")
        lines.append("【和你说话的人】")
        u = self.user_description.strip()
        lines.append(u if u else "# 你是谁、它该怎么称呼你")
        try:
            with open(self.text_file_path, "w", encoding="utf-8") as fp:
                fp.write("\n".join(lines))
        except Exception:
            return None
        return self.text_file_path

    def import_text(self):
        try:
            with open(self.text_file_path, "r", encoding="utf-8") as fp:
                raw = fp.read()
        except Exception:
            return False
        title_to_key = {f.title: f.key for f in FIELDS}
        title_to_key["和你说话的人"] = "userDesc"

        result = {}
        current = None
        buf = []

        def flush():
            if current is not None:
                result[current] = "\n".join(buf).strip()

        for line in raw.splitlines():
            s = line.strip()
            if s.startswith("【") and s.endswith("】"):
                flush()
                buf = []
                title = s[1:-1]
                current = title_to_key.get(title)
                continue
            if s.startswith("#"):
                continue
            buf.append(line)
        flush()

        if not result:
            return False
        for k, v in result.items():
            self._values[k] = v
        self.save()
        return True


role = RoleProfile()
