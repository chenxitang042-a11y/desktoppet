"""心情。移植自 Mac 版 MoodSystem。

会影响说话频率、走动倾向。根据时间、天气、活动、互动频率综合推算。
"""
import time
from datetime import datetime

# 心情 -> (说话间隔倍率, 走动倾向 0~1)
# 倍率越大越少说话;倾向越大越爱走动。
_MOOD_PARAMS = {
    "calm":    (1.0, 0.5),
    "low":     (1.6, 0.15),
    "relaxed": (0.7, 0.8),
    "focused": (2.2, 0.0),
}

_MOOD_NAME = {"calm": "平静", "low": "低落", "relaxed": "放松", "focused": "专注"}


class MoodSystem:
    def __init__(self):
        self.current = "calm"
        self._interactions = []   # 最近互动时间戳

    def record_interaction(self):
        now = time.time()
        self._interactions.append(now)
        cutoff = now - 30 * 60
        self._interactions = [t for t in self._interactions if t >= cutoff]

    def reevaluate(self, is_pomodoro, activity, weather):
        self.current = self._compute(is_pomodoro, activity, weather)
        return self.current

    def _compute(self, is_pomodoro, activity, weather):
        if is_pomodoro:
            return "focused"
        if activity == "writing":
            return "focused"

        now = datetime.now()
        hour = now.hour
        is_weekend = now.weekday() >= 5   # 5,6 = 周六日

        if hour >= 23 or hour < 5:
            return "low"
        if weather in ("rain", "snow"):
            return "low"
        if is_weekend or activity == "music":
            return "relaxed"
        if len(self._interactions) >= 4:
            return "relaxed"
        return "calm"

    @property
    def name(self):
        return _MOOD_NAME.get(self.current, "平静")

    @property
    def chatter_multiplier(self):
        return _MOOD_PARAMS.get(self.current, (1.0, 0.5))[0]

    @property
    def stroll_tendency(self):
        return _MOOD_PARAMS.get(self.current, (1.0, 0.5))[1]


mood = MoodSystem()
