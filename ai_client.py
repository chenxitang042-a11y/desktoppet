"""AI 客户端。移植自 Mac 版 AIClient.swift。

核心原则(和原版一致):**这个文件不包含任何人设。**
系统提示词完全由调用方给,原样发出去。

只依赖标准库 urllib,不用第三方 HTTP 库 —— 打包更小,少一个出错点。
"""
import json
import urllib.request
import urllib.error

from settings import settings


class Provider:
    def __init__(self, pid, name, host, model, console, note, fmt):
        self.id = pid
        self.name = name
        self.host = host
        self.model = model
        self.console = console
        self.note = note
        self.format = fmt   # "openai" 或 "anthropic"


# 和 Mac 版完全相同的服务商列表
PROVIDERS = [
    Provider("deepseek", "DeepSeek",
             "https://api.deepseek.com", "deepseek-chat",
             "platform.deepseek.com",
             "国内直连,价格低。角色扮演够用", "openai"),
    Provider("glm", "智谱 GLM",
             "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash",
             "open.bigmodel.cn",
             "glm-4-flash 免费。想演得像建议换 glm-4-plus", "openai"),
    Provider("qwen", "通义千问",
             "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus",
             "bailian.console.aliyun.com",
             "阿里出品,新账号有免费额度", "openai"),
    Provider("kimi", "Kimi",
             "https://api.moonshot.cn/v1", "moonshot-v1-8k",
             "platform.moonshot.cn",
             "长文本强", "openai"),
    Provider("siliconflow", "硅基流动",
             "https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-32B-Instruct",
             "cloud.siliconflow.cn",
             "聚合开源模型。角色扮演建议选 32B 以上", "openai"),
    Provider("openai", "OpenAI",
             "https://api.openai.com/v1", "gpt-4o-mini",
             "platform.openai.com",
             "需要能访问国外网络", "openai"),
    Provider("anthropic", "Anthropic",
             "https://api.anthropic.com", "claude-sonnet-4-20250514",
             "console.anthropic.com",
             "角色扮演质量最好,需要能访问国外网络", "anthropic"),
    Provider("ollama", "本地模型 Ollama",
             "http://127.0.0.1:11434/v1", "qwen2.5:14b",
             "ollama.com",
             "完全离线。要先装 Ollama 并下载模型,14B 以上才演得住人物", "openai"),
    Provider("custom", "自定义",
             "", "", "",
             "任何 OpenAI 兼容的接口都行", "openai"),
]


def find_provider(pid):
    for p in PROVIDERS:
        if p.id == pid:
            return p
    return PROVIDERS[0]


class AIClient:
    """发请求。所有方法同步执行 —— 界面层放到后台线程里调,别卡住 UI。"""

    @property
    def provider(self):
        return find_provider(settings.get("ai_provider"))

    @property
    def host(self):
        h = (settings.get("ai_host") or "").strip()
        base = h if h else self.provider.host
        return base[:-1] if base.endswith("/") else base

    @property
    def model(self):
        m = (settings.get("ai_model") or "").strip()
        return m if m else self.provider.model

    @property
    def api_key(self):
        return (settings.get("ai_key") or "").strip()

    @property
    def is_ready(self):
        if not settings.get("ai_enabled"):
            return False
        if self.provider.id == "ollama":
            return True
        return bool(self.api_key)

    # ---- 对外:发一次对话,返回 (回复文本, 错误信息)。成功时错误为 None ----
    def chat(self, system, messages, max_tokens=700, temperature=0.9):
        try:
            if self.provider.format == "anthropic":
                return self._call_anthropic(system, messages, max_tokens, temperature)
            return self._call_openai(system, messages, max_tokens, temperature)
        except Exception as e:
            return None, f"出错了:{e}"

    def _call_openai(self, system, messages, max_tokens, temperature):
        url = f"{self.host}/chat/completions"
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        body = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data, err = self._post(url, body, headers)
        if err:
            return None, err
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None, "返回内容为空或无法解析"
        return (text, None) if text else (None, "返回内容为空")

    def _call_anthropic(self, system, messages, max_tokens, temperature):
        url = f"{self.host}/v1/messages"
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            body["system"] = system
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        data, err = self._post(url, body, headers)
        if err:
            return None, err
        try:
            parts = [b.get("text", "") for b in data.get("content", [])]
            text = "".join(parts).strip()
        except Exception:
            return None, "返回内容无法解析"
        return (text, None) if text else (None, "返回内容为空")

    def _post(self, url, body, headers):
        raw = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                obj = json.loads(e.read().decode("utf-8"))
                detail = (obj.get("error") or {}).get("message") or obj.get("message") or ""
            except Exception:
                pass
            return None, self._friendly_error(e.code, detail)
        except urllib.error.URLError as e:
            return None, f"连不上服务器:{getattr(e, 'reason', e)}"
        except Exception as e:
            return None, f"请求失败:{e}"

    @staticmethod
    def _friendly_error(code, detail):
        hints = {
            401: "Key 不对或已失效",
            402: "余额不足,需要充值",
            403: "没有权限,检查 Key 或地区限制",
            404: "模型名可能写错了",
            429: "请求太频繁或额度用完了",
        }
        msg = f"HTTP {code}"
        if code in hints:
            msg += f"({hints[code]})"
        if detail:
            msg += f": {detail[:120]}"
        return msg

    # ---- 测试连接:一句话,不带人设 ----
    def test(self):
        text, err = self.chat(
            system="",
            messages=[{"role": "user", "content": "回复「好」两个字就行。"}],
            max_tokens=32, temperature=0.3,
        )
        if text:
            return True, f"连接正常。它回了:「{text[:60]}」"
        return False, err or "未知错误"


client = AIClient()
