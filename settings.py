"""设置。对应 Mac 版的 PetSettings。

存在 %APPDATA%\\DesktopPet\\settings.json。
"""
import json

from paths import support_path

_DEFAULTS = {
    "ai_enabled": True,
    "ai_provider": "deepseek",   # 见 ai_client.PROVIDERS
    "ai_host": "",               # 留空用服务商默认地址
    "ai_model": "",              # 留空用服务商默认模型
    "ai_key": "",
    "ai_max_tokens": 700,
    "ai_temperature": 0.9,
    "ai_memory_turns": 12,       # 保留多少轮对话再开始压缩
    "ai_add_framing_note": True, # 是否加那段"用这个身份说话"的收尾提示

    "pet_scale": 1.0,            # 角色显示倍率(原图约 98x116)
    "always_on_top": True,
}


class _Settings:
    def __init__(self):
        self._path = support_path("settings.json")
        self._data = dict(_DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in self._data:
                    self._data[k] = v
        except Exception:
            pass

    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key):
        return self._data.get(key, _DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()


settings = _Settings()
