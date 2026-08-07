"""对话服务。移植自 Mac 版 AIService.swift。

有 AI 就走模型,没有就退回关键词回应(保证「说点什么」永远有反应)。
同步执行 —— 界面层用后台线程调,别卡 UI。
"""
import random

from ai_client import client
from conversation import conversation
from role_profile import role
from settings import settings


def is_available():
    return client.is_ready


def has_role():
    return not role.is_empty


def status_text():
    if not settings.get("ai_enabled"):
        return "AI 已关闭,用关键词回应"
    if not client.is_ready:
        return f"{client.provider.name} · 还没填 Key"
    role_state = "已设定角色" if has_role() else "还没填角色设定"
    return f"{client.provider.name} · {client.model} · {role_state}"


def send(text):
    """发一句话。返回 (回复, 是不是 AI 给的)。无论走哪条都会记进历史。"""
    if not client.is_ready:
        reply = _fallback_reply(text)
        conversation.append("user", text)
        conversation.append("assistant", reply)
        return reply, False

    system = conversation.system_prompt()
    messages = conversation.build_messages(text)
    reply, _ = client.chat(
        system=system,
        messages=messages,
        max_tokens=int(settings.get("ai_max_tokens")),
        temperature=settings.get("ai_temperature"),
    )
    final = reply if reply else _fallback_reply(text)
    conversation.append("user", text)
    conversation.append("assistant", final)
    return final, (reply is not None)


def preview(text):
    """试一下。不进历史,方便反复调设定。系统提示词和真实聊天完全一样。"""
    if not client.is_ready:
        return "(还没配好 AI。设置 → 对话 里填一下。)"
    system = role.build_system_prompt()
    reply, err = client.chat(
        system=system,
        messages=[{"role": "user", "content": text}],
        max_tokens=int(settings.get("ai_max_tokens")),
        temperature=settings.get("ai_temperature"),
    )
    return reply if reply else f"失败:{err or '未知错误'}"


# ---- 没配 AI 时的兜底关键词(和 Mac 版一致)----
_RULES = [
    (["累", "好累", "疲惫", "困"], ["那休息一下。", "别硬撑。", "先停一停吧。"]),
    (["饿", "吃饭", "午饭", "晚饭"], ["去吃点东西。", "别忘了吃饭。"]),
    (["烦", "焦虑", "难受"], ["嗯,我在。", "……", "会过去的。"]),
    (["加班", "ddl", "赶工"], ["别熬太晚。", "悠着点。"]),
    (["你好", "在吗", "hi"], ["嗯,在。", "我在。"]),
    (["谢谢", "感谢"], ["不用谢。", "嗯。"]),
    (["晚安", "睡了"], ["晚安。", "早点休息。"]),
    (["早", "早安"], ["早。"]),
]
_GENERIC = ["嗯。", "……", "我在听。", "知道了。"]


def _fallback_reply(text):
    low = (text or "").lower()
    for keys, replies in _RULES:
        if any(k in low for k in keys):
            return random.choice(replies)
    return random.choice(_GENERIC)
