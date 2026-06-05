"""
场景/地点信息提取
从小说文本中识别所有场景，提取地点、时间、天气、出场角色等结构化信息
"""
import json
import re
from backend.llm_client import call_llm
from backend.errors import AppException, ErrorCode


SCENE_EXTRACT_PROMPT = """你是一位专业的文学分析师，擅长从小说文本中提取和分类场景信息。

## 任务
仔细阅读以下小说片段，识别文中所有场景/地点转换。每当故事的环境、地点或时间发生明显变化时，就是一个新场景。

## 输出格式
**严格输出 JSON 数组，不要添加任何解释文字。** 格式如下：

```json
[
  {
    "scene_index": 1,
    "location": "场景地点名称（如 青云山主峰大殿 / 长安城西市）",
    "location_type": "室内 / 室外 / 未知",
    "time_period": "时间描述（如 清晨 / 午夜 / 三年前 / 秋季傍晚）",
    "weather": "天气描述（如 晴 / 暴雨 / 大雪 / 阴 或 未知）",
    "characters_present": ["在场角色1", "在场角色2"],
    "description": "场景内容简要描述（30字以内）",
    "key_events": ["关键事件1", "关键事件2"]
  }
]
```

## 提取规则
1. **场景边界**：地点变化、时间跳跃、视角切换都视为新场景
2. **地点精确**：尽量提取原文中的具体地名，不要笼统写"某个房间"
3. **时间推断**：根据上下文推断大致时间（清晨/正午/黄昏/深夜等）
4. **天气感知**：原文提到天气则记录，未提则填"未知"
5. **出场角色**：列出该场景中出现的所有角色姓名
6. **关键事件**：提炼场景中的核心情节（如"初次相遇""大战爆发""秘密揭露"）
7. **scene_index 从 1 开始递增**

## 输出要求
只输出 JSON 数组，不要有任何其他文字。
"""


def _clean_json(text: str) -> str:
    """清洗 LLM 输出，提取 JSON 数组"""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        return match.group(0)
    return text


def _validate_scene(scene: dict, index: int) -> dict:
    """校验并补齐场景字段"""
    defaults = {
        "scene_index": index,
        "location": f"未命名场景{index}",
        "location_type": "未知",
        "time_period": "未知",
        "weather": "未知",
        "characters_present": [],
        "description": "",
        "key_events": [],
    }
    for key, default in defaults.items():
        if key not in scene or scene[key] is None:
            scene[key] = default
    # 类型纠正
    if not isinstance(scene.get("characters_present"), list):
        scene["characters_present"] = []
    if not isinstance(scene.get("key_events"), list):
        scene["key_events"] = []
    # 合法值约束
    if scene["location_type"] not in ("室内", "室外", "未知"):
        scene["location_type"] = "未知"
    # 覆盖 scene_index 保证连续
    scene["scene_index"] = index
    return scene


def extract_scenes(text: str) -> dict:
    """从小说文本中提取场景列表

    Args:
        text: 小说原文

    Returns:
        {
            "scenes": [...],
            "total": int,
            "location_distribution": {"室内": n, "室外": n, "未知": n},
            "all_locations": [...],
            "all_characters_mentioned": [...]
        }
    """
    raw = call_llm(SCENE_EXTRACT_PROMPT, f"## 小说原文\n\n{text}")
    cleaned = _clean_json(raw)

    try:
        scenes = json.loads(cleaned)
    except json.JSONDecodeError:
        raise AppException(
            ErrorCode.LLM_PARSE_ERROR,
            f"场景列表 JSON 解析失败。LLM 原始输出片段: {raw[:200]}"
        )

    if not isinstance(scenes, list):
        raise AppException(ErrorCode.LLM_PARSE_ERROR, "LLM 输出的不是数组格式")

    # 校验每个场景
    scenes = [_validate_scene(s, i + 1) for i, s in enumerate(scenes) if isinstance(s, dict)]

    # 统计分布
    location_dist = {"室内": 0, "室外": 0, "未知": 0}
    all_locations = []
    all_characters = set()

    for s in scenes:
        lt = s.get("location_type", "未知")
        if lt in location_dist:
            location_dist[lt] += 1
        all_locations.append(s.get("location", ""))
        for c in s.get("characters_present", []):
            if c and isinstance(c, str):
                all_characters.add(c)

    return {
        "scenes": scenes,
        "total": len(scenes),
        "location_distribution": location_dist,
        "all_locations": all_locations,
        "all_characters_mentioned": sorted(all_characters),
    }
