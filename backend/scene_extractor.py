"""
场景/地点信息提取（全中文字段名）
从小说文本中识别所有场景，提取地点、时间、天气、出场角色等结构化信息
"""
import json
import os
import re
import datetime
from backend.llm_client import call_llm
from backend.errors import AppException, ErrorCode
from backend.json_utils import parse_llm_json


SCENE_EXTRACT_PROMPT = """你是一位专业的文学分析师，擅长从小说文本中提取和分类场景信息。

## 任务
仔细阅读以下小说片段，识别文中所有场景/地点转换。每当故事的环境、地点或时间发生明显变化时，就是一个新场景。

## 输出格式
**严格输出 JSON 数组，不要添加任何解释文字。** 格式如下：

```json
[
  {
    "场景序号": 1,
    "地点": "场景地点名称（如 青云山主峰大殿 / 长安城西市）",
    "地点类型": "室内 / 室外 / 未知",
    "时间段": "时间描述（如 清晨 / 午夜 / 三年前 / 秋季傍晚）",
    "天气": "天气描述（如 晴 / 暴雨 / 大雪 / 阴 或 未知）",
    "在场角色": ["在场角色1", "在场角色2"],
    "描述": "场景内容简要描述（30字以内）",
    "关键事件": ["关键事件1", "关键事件2"]
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
7. **场景序号 从 1 开始递增**

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
        "场景序号": index,
        "地点": f"未命名场景{index}",
        "地点类型": "未知",
        "时间段": "未知",
        "天气": "未知",
        "在场角色": [],
        "描述": "",
        "关键事件": [],
    }
    for key, default in defaults.items():
        if key not in scene or scene[key] is None:
            scene[key] = default
    # 类型纠正
    if not isinstance(scene.get("在场角色"), list):
        scene["在场角色"] = []
    if not isinstance(scene.get("关键事件"), list):
        scene["关键事件"] = []
    # 合法值约束
    if scene["地点类型"] not in ("室内", "室外", "未知"):
        scene["地点类型"] = "未知"
    # 覆盖 场景序号 保证连续
    scene["场景序号"] = index
    return scene


def extract_scenes(text: str) -> dict:
    """从小说文本中提取场景列表

    Args:
        text: 小说原文

    Returns:
        {
            "场景列表": [...],
            "总数": int,
            "地点分布": {"室内": n, "室外": n, "未知": n},
            "所有地点": [...],
            "所有提及角色": [...]
        }
    """
    raw = call_llm(SCENE_EXTRACT_PROMPT, f"## 小说原文\n\n{text}")
    cleaned = _clean_json(raw)

    try:
        scenes = parse_llm_json(cleaned)
    except json.JSONDecodeError:
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            log_path = os.path.join(log_dir, f"scene_parse_error_{ts}.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"=== LLM Raw Output ({len(raw)} chars) ===\n")
                f.write(raw)
                f.write(f"\n\n=== Cleaned ({len(cleaned)} chars) ===\n")
                f.write(cleaned)
        except Exception:
            log_path = "N/A"
        raise AppException(
            ErrorCode.LLM_PARSE_ERROR,
            f"场景列表 JSON 解析失败。调试日志: {log_path}\nLLM 原始输出片段: {raw[:200]}"
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
        lt = s.get("地点类型", "未知")
        if lt in location_dist:
            location_dist[lt] += 1
        all_locations.append(s.get("地点", ""))
        for c in s.get("在场角色", []):
            if c and isinstance(c, str):
                all_characters.add(c)

    return {
        "场景列表": scenes,
        "总数": len(scenes),
        "地点分布": location_dist,
        "所有地点": all_locations,
        "所有提及角色": sorted(all_characters),
    }
