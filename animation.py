"""动画定义。

把 PetImages 里的帧按动作分组,给每个状态一套帧序列和播放速度。
帧文件名参照 Mac 版素材,原样沿用。
"""
import os

from paths import images_dir

# 每个状态: (帧文件名列表, 每帧毫秒, 是否循环)
# 单帧的动作(talk/stretch/dragged)靠 1 帧 + 不循环表现静态姿势。
STATES = {
    "idle":       (["idle_001.png", "idle_002.png", "idle_003.png"], 420, True),
    "blink":      (["blink_001.png", "blink_002.png", "blink_003.png", "blink_004.png"], 90, False),
    "walk":       (["walk_001.png", "walk_002.png", "walk_003.png", "walk_004.png",
                    "walk_005.png", "walk_006.png", "walk_007.png", "walk_008.png"], 110, True),
    "read":       (["read_001.png", "read_002.png", "read_003.png",
                    "read_004.png", "read_005.png", "read_006.png"], 360, True),
    "sleep":      (["sleep_001.png", "sleep_002.png", "sleep_003.png", "sleep_004.png"], 600, True),
    "think":      (["think_001.png", "think_002.png", "think_003.png"], 380, True),
    "wave":       (["wave_001.png", "wave_002.png"], 260, False),
    "headphones": (["headphones_001.png", "headphones_002.png",
                    "headphones_003.png", "headphones_004.png"], 300, True),
    "glasses":    (["glasses_001.png", "glasses_002.png", "glasses_003.png",
                    "glasses_004.png", "glasses_005.png", "glasses_006.png"], 300, True),
    "stretch":    (["stretch_001.png"], 900, False),
    "talk":       (["talk.png"], 400, True),
    "dragged":    (["dragged.png"], 400, True),
}

# 待机时会随机穿插的小动作,让它显得"活着"
IDLE_BEHAVIORS = ["blink", "read", "think", "stretch", "wave", "headphones", "glasses", "sleep"]


def frame_paths(state):
    frames, _, _ = STATES.get(state, STATES["idle"])
    d = images_dir()
    out = []
    for name in frames:
        p = os.path.join(d, name)
        if os.path.exists(p):
            out.append(p)
    if not out:  # 万一素材缺失,退回 idle 单帧,别崩
        fallback = os.path.join(d, "idle.png")
        if os.path.exists(fallback):
            out = [fallback]
    return out


def frame_interval(state):
    return STATES.get(state, STATES["idle"])[1]


def loops(state):
    return STATES.get(state, STATES["idle"])[2]
