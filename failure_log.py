"""数据获取失败的登记处。移植自 Mac 版 FailureLog。

失败时(比如天气拉不到、AI 报错)登记一笔,不弹框打扰。
桌宠会在合适时机含糊提一句(「好像忘了什么」),想看具体原因去设置里看。
功能恢复正常会自动清掉对应记录。
"""
import time
from datetime import datetime


class FailureLog:
    def __init__(self):
        self._entries = []       # [(source, detail, ts)]
        self._unreported = False
        self._last_hint_at = 0.0

    def record(self, source, detail):
        self._entries.insert(0, (source, detail, time.time()))
        self._entries = self._entries[:20]
        self._unreported = True

    def clear(self, source):
        self._entries = [e for e in self._entries if e[0] != source]
        if not self._entries:
            self._unreported = False

    def should_hint(self):
        """有没报过的失败,且距上次提示超过 30 分钟,才返回 True。"""
        if not self._unreported:
            return False
        if time.time() - self._last_hint_at < 30 * 60:
            return False
        self._last_hint_at = time.time()
        self._unreported = False
        return True

    def summary(self):
        if not self._entries:
            return "暂时没有问题。"
        lines = []
        for source, detail, ts in self._entries[:8]:
            when = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
            lines.append(f"{when}  {source}: {detail}")
        return "\n".join(lines)


failure_log = FailureLog()
