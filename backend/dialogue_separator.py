"""
对白与叙述文本分离（全中文字段名）
从小说文本中区分对话和描写，标记每条对话的发言者
"""
import json
import os
import re
import datetime
from backend.llm_client import call_llm
from backend.errors import AppException, ErrorCode
from backend.json_utils import parse_llm_json


DIALOGUE_EXTRACT_PROMPT = """你是一位专业的文学分析师，擅长从小说文本中分离对话与叙述。

## 任务
仔细阅读以下小说片段，识别所有对话（双引号内或明显的角色说话内容），并区分叙述性文字。

## 输出格式
**严格输出 JSON 对象，不要添加任何解释文字。** 格式如下：

```json
{
  "片段列表": [
    {
      "序号": 1,
      "类型": "对话",
      "发言者": "李青云",
      "内容": "完整对话内容（不含引号）",
      "引号风格": "双引号 / 单引号 / 无引号",
      "语气": "语气（如 平静 / 激动 / 愤怒 / 无奈 / 正常）"
    },
    {
      "序号": 2,
      "类型": "叙述",
      "内容": "叙述内容（动作描写、环境描写、心理活动等）",
      "描述": "叙述类型简述（如 打斗场景 / 环境描写 / 心理独白）"
    }
  ]
}
```

## 提取规则
1. **对话识别**：双引号、单引号包裹的内容，或"XX道/XX说/XX喊"引导的内容
2. **发言者标记**：根据上下文推断说话人姓名，无法确定时填"未知"
3. **内心独白**：角色内心活动（如"他想""心中暗道"）标记为 对话，发言者 为该角色，引号风格 填"无引号"
4. **语气感知**：根据上下文和标点推断说话语气（感叹号=激动，省略号=犹豫，反问=质疑）
5. **叙述内容**：非对话的描写、背景介绍、动作细节、环境渲染等
6. **序号 从 1 开始递增**
7. **保持原文顺序**，对话和叙述交替出现的顺序要和原文一致

## 输出要求
只输出 JSON 对象，不要有任何其他文字。
"""


def _clean_json(text: str) -> str:
    """清洗 LLM 输出，提取 JSON 对象"""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    # 提取最外层 JSON 对象
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)
    return text


def _validate_segment(segment: dict, index: int) -> dict:
    """校验并补齐片段字段"""
    seg_type = segment.get("类型", "叙述")
    if seg_type not in ("对话", "叙述"):
        seg_type = "叙述"

    defaults = {
        "序号": index,
        "类型": seg_type,
        "内容": "",
        "发言者": "",
        "引号风格": "无引号",
        "语气": "正常",
        "描述": "",
    }

    for key, default in defaults.items():
        if key not in segment or segment[key] is None:
            segment[key] = default

    # 类型纠正
    if seg_type == "叙述":
        segment.setdefault("描述", segment.get("内容", "")[:50])
        # 叙述段不需要 发言者/语气/引号风格，但保留不删
    elif seg_type == "对话":
        if "发言者" not in segment or not segment.get("发言者"):
            segment["发言者"] = "未知"
        if segment.get("引号风格") not in ("双引号", "单引号", "无引号"):
            segment["引号风格"] = "无引号"

    segment["序号"] = index
    return segment


def extract_dialogue(text: str) -> dict:
    """从小说文本中分离对白与叙述

    Args:
        text: 小说原文

    Returns:
        {
            "片段列表": [...],
            "总数": int,
            "对话数": int,
            "叙述数": int,
            "发言者分布": {speaker: count, ...},
            "对话占比": float  (0-1)
        }
    """
    raw = call_llm(DIALOGUE_EXTRACT_PROMPT, f"## 小说原文\n\n{text}")
    cleaned = _clean_json(raw)

    try:
        data = parse_llm_json(cleaned)
    except json.JSONDecodeError:
        # 写入调试日志
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            log_path = os.path.join(log_dir, f"dialogue_parse_error_{ts}.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"=== LLM Raw Output ({len(raw)} chars) ===\n")
                f.write(raw)
                f.write(f"\n\n=== Cleaned ({len(cleaned)} chars) ===\n")
                f.write(cleaned)
        except Exception:
            log_path = "N/A"
        raise AppException(
            ErrorCode.LLM_PARSE_ERROR,
            f"对话分离 JSON 解析失败。调试日志: {log_path}\nLLM 原始输出片段: {raw[:200]}"
        )

    if not isinstance(data, dict):
        raise AppException(ErrorCode.LLM_PARSE_ERROR, "LLM 输出的不是 JSON 对象")

    segments_raw = data.get("片段列表", [])
    if not isinstance(segments_raw, list):
        raise AppException(ErrorCode.LLM_PARSE_ERROR, "片段列表 字段不是数组")

    # 校验每个片段
    segments = [_validate_segment(s, i + 1) for i, s in enumerate(segments_raw) if isinstance(s, dict)]

    # 统计
    dialogue_count = sum(1 for s in segments if s["类型"] == "对话")
    narration_count = sum(1 for s in segments if s["类型"] == "叙述")

    # 发言者分布
    speaker_dist: dict[str, int] = {}
    for s in segments:
        if s["类型"] == "对话" and s.get("发言者"):
            sp = s["发言者"]
            speaker_dist[sp] = speaker_dist.get(sp, 0) + 1

    total = len(segments)
    dialogue_ratio = dialogue_count / total if total > 0 else 0

    return {
        "片段列表": segments,
        "总数": total,
        "对话数": dialogue_count,
        "叙述数": narration_count,
        "发言者分布": speaker_dist,
        "对话占比": round(dialogue_ratio, 3),
    }
