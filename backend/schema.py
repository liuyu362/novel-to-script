"""
剧本 Schema 的 Python 数据类定义
与 schema.yaml 保持一致，供后端序列化/反序列化使用
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Act:
    """场景中的一个动作/对话单元"""
    type: str           # action | dialogue | direction
    content: str        # 内容文本
    character: str = ""  # 关联角色名
    emotion: str = ""    # 情绪/语气
    note: str = ""       # 补充说明


@dataclass
class Character:
    """角色信息"""
    id: int
    name: str
    aliases: list[str] = field(default_factory=list)
    gender: str = ""
    age: str = ""
    role_type: str = ""          # 主角 | 配角 | 反派 | 路人
    description: str = ""
    first_appearance: int = 0    # 首次出场场景ID


@dataclass
class Scene:
    """单个场景"""
    id: int
    name: str
    location: str = ""
    time: str = ""
    weather: str = ""
    characters: list[str] = field(default_factory=list)
    acts: list[Act] = field(default_factory=list)


@dataclass
class Meta:
    """剧本元信息"""
    title: str = ""
    source_title: str = ""
    version: str = "movie"       # movie | tv_series | stage_play
    total_scenes: int = 0
    character_count: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Script:
    """剧本顶层结构"""
    meta: Meta = field(default_factory=Meta)
    characters: list[Character] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转为字典（用于 YAML 序列化）"""
        return asdict(self)

    def stats(self) -> dict:
        """快速统计"""
        return {
            "scenes": len(self.scenes),
            "characters": len(self.characters),
            "total_acts": sum(len(s.acts) for s in self.scenes),
            "dialogue_count": sum(
                sum(1 for a in s.acts if a.type == "dialogue")
                for s in self.scenes
            ),
            "action_count": sum(
                sum(1 for a in s.acts if a.type == "action")
                for s in self.scenes
            ),
        }


# 已实现的剧本版本列表
SCRIPT_VERSIONS = {
    "movie": {
        "name": "电影版",
        "description": "2小时时长，紧凑节奏，视觉化优先",
    },
    "tv_series": {
        "name": "电视剧版",
        "description": "多集分季，细腻展开，注重角色成长",
    },
    "stage_play": {
        "name": "舞台剧版",
        "description": "有限场景，强化对话冲突，适合现场演出",
    },
}

