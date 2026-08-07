"""对话与记忆。移植自 Mac 版 Conversation.swift。

聊天记录存本机,重启不丢。
超出保留轮数的老对话压成一段概要,避免上下文撑爆。
"""
import json
import time

from paths import support_path
from settings import settings
from ai_client import client
from role_profile import role


class Conversation:
    def __init__(self):
        self._path = support_path("chat.json")
        self.messages = []   # [{"role","content","date"}]
        self.summary = ""
        self.load()

    @property
    def turn_count(self):
        return sum(1 for m in self.messages if m["role"] == "user")

    def append(self, role_, content):
        t = (content or "").strip()
        if not t:
            return
        self.messages.append({"role": role_, "content": t, "date": time.time()})
        self._trim_if_needed()
        self.save()

    def clear(self):
        self.messages = []
        self.summary = ""
        self.save()

    def build_messages(self, new_input):
        """拼出这次要发的消息列表。概要作为第一轮对话带上。"""
        out = []
        if self.summary:
            out.append({"role": "user", "content": f"(之前聊过的:{self.summary})"})
            out.append({"role": "assistant", "content": "嗯。"})
        for m in self.messages:
            out.append({"role": m["role"], "content": m["content"]})
        out.append({"role": "user", "content": new_input})
        return out

    def system_prompt(self):
        return role.build_system_prompt()

    # ---- 压缩 ----
    def _trim_if_needed(self):
        keep = max(4, int(settings.get("ai_memory_turns")) * 2)
        if len(self.messages) <= keep:
            return
        overflow = len(self.messages) - keep
        old = self.messages[:overflow]
        self.messages = self.messages[overflow:]

        if client.is_ready:
            self._summarize_with_ai(old)
        else:
            self._summarize_simply(old)

    def _summarize_simply(self, old):
        lines = [m["content"][:40] for m in old if m["role"] == "user"]
        if not lines:
            return
        s = (self.summary + " ") if self.summary else ""
        s += ";".join(lines)
        self.summary = s[-400:]

    def _summarize_with_ai(self, old):
        text = "\n".join(
            ("对方:" if m["role"] == "user" else "你:") + m["content"] for m in old
        )
        prompt = (
            "下面是之前的对话。压缩成不超过 150 字的概要,\n"
            "只保留以后还用得上的信息,丢掉寒暄。直接输出概要。\n\n"
            f"已有概要:{self.summary or '(无)'}\n\n"
            f"对话:\n{text}"
        )
        # 压缩是工具活,用空系统提示词,不带角色口吻
        reply, _ = client.chat(system="",
                               messages=[{"role": "user", "content": prompt}],
                               max_tokens=300, temperature=0.3)
        if reply:
            self.summary = reply[:400]
        else:
            self._summarize_simply(old)

    # ---- 持久化 ----
    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"messages": self.messages, "summary": self.summary},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.messages = d.get("messages", [])
            self.summary = d.get("summary", "")
        except Exception:
            self.messages = []
            self.summary = ""


conversation = Conversation()
