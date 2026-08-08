"""场景台词。移植自 Mac 版 RoleLines.swift。

点击、问候、番茄钟这些场景说的话,全部拿用户填的角色设定让 AI 现生成,
**不写死人设**。生成用的系统提示词就是 RoleProfile 里用户填的内容,
和聊天完全同一套 —— 所以人设一改,台词跟着变。

一次生成,之后用缓存。角色改了自动重生成。
生成是网络请求,放后台线程,不卡界面。
"""
import json
import random
import re
import threading

from paths import support_path
from settings import settings
from ai_client import client
from role_profile import role


# 用来切分"被挤在一行里的多句台词"的分隔符
_SPLIT_RE = re.compile(r"\s*[/／|｜、;；]\s*|\s{2,}")


def _split_options(text):
    """把 '哦?/要去哪/喔——' 这种拆成多句;正常单句原样返回。"""
    parts = [p for p in _SPLIT_RE.split(text) if p.strip()]
    return parts if len(parts) > 1 else [text]


def _one_utterance(text):
    """兜底:无论如何只取一句短的,防止一次冒出一大串。"""
    if not text:
        return text
    first = text.replace("\r", "\n").split("\n")[0].strip()
    parts = _split_options(first)
    out = parts[0].strip() if parts else first
    return out[:30]


# 需要生成台词的场景:标识 -> 情境说明。说明写清楚,生成才贴合。
SCENES = [
    ("click",          "对方点了你一下想引起你注意"),
    ("click_again",    "对方连着戳了你三四次了"),
    ("click_toomuch",  "对方还在没完没了地戳你"),
    ("pickup",         "对方把你拎起来了"),
    ("drop",           "对方把你放下了"),
    ("greet_morning",  "早上,你们刚开始今天的相处"),
    ("greet_afternoon","下午,你们刚开始今天的相处"),
    ("greet_evening",  "傍晚,你们刚开始今天的相处"),
    ("greet_night",    "深夜了,对方才刚打开电脑"),
    ("chatter",        "你突然想跟对方说句话,没什么正事"),
    ("night",          "已经很晚了,对方还没睡"),
    ("overwork",       "对方连续工作很久没休息"),
    ("idle_sit",       "你在旁边安静待着,没什么特别的事"),
    ("pomodoro_start", "对方开始一段专注工作,你陪着"),
    ("pomodoro_end",   "对方的专注时间结束了,该休息"),
    ("break_start",    "休息时间开始,你想让对方起来动动"),
    ("break_end",      "休息结束,你在问要不要继续"),
    ("milestone",      "你们认识已经有一段时间了,你想提一句"),
    ("activity_music",   "你注意到对方在听歌"),
    ("activity_writing", "你注意到对方在专心打字、写东西或写代码"),
    ("activity_browsing","你注意到对方在看网页或看文档"),
    ("battery_low",      "对方的电脑快没电了"),
    ("reminder_due",     "到了之前约好提醒对方的时间"),
    ("reminder_set",     "对方让你到某个时间提醒他,你答应了"),
    ("weather_rain",     "外面在下雨"),
    ("weather_snow",     "外面在下雪"),
    ("rare",             "很偶尔的时候你想说点什么:一个念头、一句感慨"),
]

# 没配 AI / 没填人设时,最朴素的兜底(尽量少,主要还是靠 AI 生成)
_FALLBACK = {
    "click":          ["怎么了", "嗯?", "在呢"],
    "click_again":    ["还有事?", "怎么啦", "嗯嗯"],
    "click_toomuch":  ["别戳啦", "……", "好啦好啦"],
    "pickup":         ["哦?", "要去哪", "喔——"],
    "drop":           ["好", "落地了", "嗯"],
    "greet_morning":  ["早", "早上好"],
    "greet_afternoon":["下午好", "在忙?"],
    "greet_evening":  ["傍晚了", "回来啦"],
    "greet_night":    ["这么晚还在", "夜猫子"],
    "chatter":        ["在想事情", "嗯……", "没什么"],
    "night":          ["该睡了", "别熬太晚"],
    "overwork":       ["歇会儿吧", "起来动动"],
    "idle_sit":       ["……", "我在这儿", "嗯"],
    "pomodoro_start": ["开始吧,我陪你", "专注一会儿"],
    "pomodoro_end":   ["时间到,歇会儿", "辛苦了"],
    "break_start":    ["起来走两步", "放松一下"],
    "break_end":      ["继续?", "准备好了吗"],
    "milestone":      ["有些日子了", "认识挺久了"],
    "activity_music":   ["在听歌?", "什么歌", "戴上耳机咯"],
    "activity_writing": ["在忙正事", "专心点,我不吵你", "写吧写吧"],
    "activity_browsing":["在看什么", "别光看,歇会儿眼", "有意思吗"],
    "battery_low":      ["快没电了", "该充电了", "记得插电"],
    "reminder_due":     ["时间到了", "到点啦", "该做那件事了"],
    "reminder_set":     ["记下了", "好,到点提醒你", "放心"],
    "weather_rain":     ["下雨了", "外面在下雨", "记得带伞"],
    "weather_snow":     ["下雪了", "外面下雪了", "天冷"],
    "rare":             ["刚才走神了", "就这样待着也挺好", "窗外的光变了"],
}


class RoleLines:
    def __init__(self):
        self._path = support_path("role_lines.json")
        self._fingerprint = ""
        self._lines = {}          # scene -> [句子]
        self._used = {}           # scene -> set(用过的)
        self._generating = False
        self.load()

    def _current_fingerprint(self):
        return str(hash(role.build_system_prompt()))

    @property
    def is_ready(self):
        return (self._fingerprint == self._current_fingerprint()
                and bool(self._lines))

    def status_text(self):
        if role.is_empty:
            return "还没填角色设定"
        if not settings.get("ai_scene_lines"):
            return "已关闭,用内置台词"
        if not client.is_ready:
            return "需要先配好 AI"
        if self._generating:
            return "正在按你的设定生成…"
        if not self.is_ready:
            return "待生成(会自动进行)"
        n = sum(len(v) for v in self._lines.values())
        return f"已生成 {n} 句"

    def line(self, scene):
        """取一句。配了 AI 且生成好就用角色台词,否则退回内置兜底。"""
        use_ai = settings.get("ai_scene_lines") and not role.is_empty
        if use_ai:
            if self._fingerprint != self._current_fingerprint():
                self.generate_if_needed()   # 设定变了,后台重生成,这次先用兜底
            elif not self._lines.get(scene):
                self.generate_if_needed()
            else:
                return self._pick(scene, self._lines[scene])
        pool = _FALLBACK.get(scene)
        return self._pick(scene, pool) if pool else None

    def _pick(self, scene, pool):
        used = self._used.get(scene, set())
        candidates = [s for s in pool if s not in used]
        if not candidates:
            used = set()
            candidates = pool
        picked = random.choice(candidates)
        used.add(picked)
        self._used[scene] = used
        return _one_utterance(picked)

    # ---- 生成(后台线程)----
    def generate_if_needed(self):
        if self.is_ready or self._generating:
            return
        self.generate()

    def regenerate(self):
        self._fingerprint = ""
        self._lines = {}
        self._used = {}
        self.save()
        self.generate()

    def generate(self):
        if (not settings.get("ai_scene_lines") or role.is_empty
                or not client.is_ready or self._generating):
            return
        self._generating = True
        t = threading.Thread(target=self._do_generate, daemon=True)
        t.start()

    def _do_generate(self):
        try:
            fingerprint = self._current_fingerprint()
            listing = "\n".join(f"{sid}|{desc}" for sid, desc in SCENES)
            prompt = (
                "下面列出一些情境。为每个情境写 4 句你会说的话。\n\n"
                "格式:每行一句,标识和内容用竖线分开\n"
                "click|怎么了\n"
                "night|该睡了\n\n"
                "要求:\n"
                "- 用你自己的措辞和语气\n"
                "- 每句都短,像日常说话\n"
                "- 同一情境的四句要有区别\n"
                "- 不要旁白、不要动作描写、不要引号、不要编号\n"
                f"- 一共 {len(SCENES)} 个情境,每个 4 句\n\n"
                f"情境(标识|说明):\n{listing}"
            )
            # 系统提示词 = 用户填的角色设定,原样
            reply, _ = client.chat(
                system=role.build_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000, temperature=0.9,
            )
            if not reply:
                return
            valid = {sid for sid, _ in SCENES}
            parsed = {}
            for raw in reply.splitlines():
                line = raw.strip()
                if "|" not in line or line.startswith("#"):
                    continue
                sid, _, content = line.partition("|")
                sid = sid.strip()
                content = content.strip()
                if sid in valid and content:
                    for piece in _split_options(content):
                        piece = piece.strip().strip("「」\"'·-*. 0123456789")
                        if piece and len(piece) <= 30:
                            parsed.setdefault(sid, []).append(piece)
            if parsed:
                self._fingerprint = fingerprint
                self._lines = parsed
                self._used = {}
                self.save()
        finally:
            self._generating = False

    # ---- 持久化 ----
    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"fingerprint": self._fingerprint, "lines": self._lines},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self._fingerprint = d.get("fingerprint", "")
            self._lines = d.get("lines", {})
        except Exception:
            self._fingerprint = ""
            self._lines = {}

    # ---- 导出台词编辑 / 读回 ----
    @property
    def text_file_path(self):
        return support_path("角色台词.txt")

    def export_for_editing(self):
        if not self._lines:
            return None
        out = ["# 场景台词(按你的角色设定生成的)",
               "# 格式: 场景标识|台词",
               "# 改完保存,回窗口点「读回台词」。想重新生成点「重新生成台词」。",
               ""]
        desc = {sid: d for sid, d in SCENES}
        for sid in [s for s, _ in SCENES]:
            pool = self._lines.get(sid)
            if not pool:
                continue
            out.append(f"# {desc.get(sid, sid)}")
            for line in pool:
                out.append(f"{sid}|{line}")
            out.append("")
        try:
            with open(self.text_file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(out))
        except Exception:
            return None
        return self.text_file_path

    def import_from_editing(self):
        try:
            with open(self.text_file_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            return False
        parsed = {}
        for line in raw.splitlines():
            s = line.strip()
            if s.startswith("#") or "|" not in s:
                continue
            sid, _, content = s.partition("|")
            sid = sid.strip()
            content = content.strip()
            if content:
                parsed.setdefault(sid, []).append(content)
        if not parsed:
            return False
        self._lines = parsed
        self._fingerprint = self._current_fingerprint()
        self._used = {}
        self.save()
        return True


role_lines = RoleLines()
