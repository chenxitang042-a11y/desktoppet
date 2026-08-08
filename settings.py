"""设置。对应 Mac 版的 PetSettings。

存在 %APPDATA%\\DesktopPet\\settings.json。
"""
import json

from paths import support_path

_DEFAULTS = {
    "ai_enabled": True,
    "ai_provider": "deepseek",
    "ai_host": "",
    "ai_model": "",
    "ai_key": "",
    "ai_max_tokens": 700,
    "ai_temperature": 0.9,
    "ai_memory_turns": 12,
    "ai_add_framing_note": True,
    "ai_scene_lines": True,

    # 陪伴 - 番茄钟
    "pomodoro_enabled": True,
    "pomodoro_focus": 25,
    "pomodoro_break": 5,
    # 陪伴 - 护眼
    "eye_rest_enabled": False,
    "eye_rest_interval": 20,
    # 陪伴 - 提醒
    "night_mode": True,
    "sedentary_reminder": True,
    "watch_battery": True,
    "rare_enabled": True,
    # 陪伴 - 天气与节日
    "weather_enabled": True,
    "festival_enabled": True,
    "birthday": "",
    # 陪伴 - 移动
    "auto_stroll": True,
    "edge_rest": True,
    "move_speed": 50,
    # 陪伴 - 系统感知
    "lock_sleep": True,
    "fullscreen_hide": True,
    # 陪伴 - 鼠标互动
    "mouse_interact": False,
    # 陪伴 - 发呆
    "idle_sit": True,
    "idle_wait_min": 5,
    # 陪伴 - 主动搭话
    "chatter_freq": "normal",     # none / few / normal / more
    # 陪伴 - 安静时段
    "quiet_enabled": False,
    "quiet_start": 22,
    "quiet_end": 8,
    # 陪伴 - 感知与心情
    "watch_activity": True,
    "mood_enabled": True,
    "greet_on_start": True,

    # 外观
    "clothing": "hoodie",         # hoodie / polo / jacket
    "pet_scale": 1.5,
    "opacity": 0.95,

    # 其它
    "always_on_top": True,
    "autostart": False,
    "click_to_talk": True,
    "show_in_taskbar": False,
    "failure_hint": True,

    # 名字(与角色设定联动)
    "user_name": "",
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
