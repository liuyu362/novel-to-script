"""
剧本 Schema 的 Python 数据类定义（全中文字段名）
与 schema.yaml 保持一致，供后端序列化/反序列化使用
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Act:
    """场景中的一个动作/对话单元"""
    类型: str           # 动作 | 对白 | 导演指示
    文本: str           # 内容文本
    角色: str = ""      # 关联角色名
    情绪: str = ""      # 情绪/语气
    备注: str = ""      # 补充说明
    景别: str = ""      # 镜头景别：远景/全景/中景/近景/特写/大特写
    角度: str = ""      # 拍摄角度：平视/俯视/仰视/鸟瞰/倾斜
    运动: str = ""      # 镜头运动：固定/推/拉/摇/移/跟/升降/手持
    入场: str = ""      # 角色入场描述（该角色在此动作首次进入场景）
    退场: str = ""      # 角色退场描述（该角色在此动作离开场景）


@dataclass
class Character:
    """角色信息"""
    编号: int
    姓名: str
    别名: list[str] = field(default_factory=list)
    性别: str = ""
    年龄: str = ""
    角色类型: str = ""          # 主角 | 配角 | 反派 | 路人
    描述: str = ""
    首次出场: int = 0           # 首次出场场景编号


@dataclass
class Scene:
    """单个场景"""
    编号: int
    名称: str
    地点: str = ""
    时间: str = ""
    天气: str = ""
    出场角色: list[str] = field(default_factory=list)
    内容: list[Act] = field(default_factory=list)
    场景标题行: str = ""     # 标准 slugline：内景/外景. 地点 - 时间（如 "内景. 咖啡馆 - 日"）
    转场: str = ""           # 转场方式：切至/淡入淡出/淡入/淡出/叠化/划像/黑场


@dataclass
class Meta:
    """剧本元信息"""
    标题: str = ""
    原著作: str = ""
    版本: str = "电影版"       # 电影版 | 电视剧版 | 舞台剧版
    总场景数: int = 0
    角色数量: int = 0
    生成时间: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Script:
    """剧本顶层结构"""
    元信息: Meta = field(default_factory=Meta)
    角色列表: list[Character] = field(default_factory=list)
    场景列表: list[Scene] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转为字典（用于 YAML 序列化）"""
        return asdict(self)

    def stats(self) -> dict:
        """快速统计"""
        return {
            "场景数": len(self.场景列表),
            "角色数": len(self.角色列表),
            "总内容条数": sum(len(s.内容) for s in self.场景列表),
            "对白条数": sum(
                sum(1 for a in s.内容 if a.类型 == "对白")
                for s in self.场景列表
            ),
            "动作条数": sum(
                sum(1 for a in s.内容 if a.类型 == "动作")
                for s in self.场景列表
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
