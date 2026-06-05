"""
对白与叙述文本分离
从小说文本中区分对话和描写，标记每条对话的发言者
"""
import json
import re
from backend.llm_client import call_llm
from backend.errors import AppException, ErrorCode


DIALOGUE_EXTRACT_PROMPT = """你是一位专业的文学分析师，擅长从小说文本中分离对话与叙述。

## 任务
仔细阅读以下小说片段，识别所有对话（双引号内或明显的角色说话内容），并区分叙述性文字。

## 输出格式
**严格输出 JSON 对象，不要添加任何解释文字。** 格式如下：

```json
{
  "segments": [
    {
      "index": 1,
      "type": "dialogue",
      "speaker": "李青云",
      "content": "完整对话内容（不含引号）",
      "quote_style": "双引号 / 单引号 / 无引号",
      "tone": "语气（如 平静 / 激动 / 愤怒 / 无奈 / 正常）"
    },
    {
      "index": 2,
      "type": "narration",
      "content": "叙述内容（动作描写、环境描写、心理活动等）",
      "description": "叙述类型简述（如 打斗场景 / 环境描写 / 心理独白）"
    }
  ]
}
```

## 提取规则
1. **对话识别**：双引号、单引号包裹的内容，或"XX道/XX说/XX喊"引导的内容
2. **发言者标记**：根据上下文推断说话人姓名，无法确定时填"未知"
3. **内心独白**：角色内心活动（如"他想""心中暗道"）标记为 dialogue，speaker 为该角色，quote_style 填"无引号"
4. **语气感知**：根据上下文和标点推断说话语气（感叹号=激动，省略号=犹豫，反问=质疑）
5. **叙述内容**：非对话的描写、背景介绍、动作细节、环境渲染等
6. **index 从 1 开始递增**
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
    seg_type = segment.get("type", "narration")
    if seg_type not in ("dialogue", "narration"):
        seg_type = "narration"

    defaults = {
        "index": index,
        "type": seg_type,
        "content": "",
        "speaker": "",
        "quote_style": "无引号",
        "tone": "正常",
        "description": "",
    }

    for key, default in defaults.items():
        if key not in segment or segment[key] is None:
            segment[key] = default

    # 类型纠正
    if seg_type == "narration":
        segment.setdefault("description", segment.get("content", "")[:50])
        # 叙述段不需要 speaker/tone/quote_style，但保留不删
    elif seg_type == "dialogue":
        if "speaker" not in segment or not segment.get("speaker"):
            segment["speaker"] = "未知"
        if segment.get("quote_style") not in ("双引号", "单引号", "无引号"):
            segment["quote_style"] = "无引号"

    segment["index"] = index
    return segment


def extract_dialogue(text: str) -> dict:
    """从小说文本中分离对白与叙述

    Args:
        text: 小说原文

    Returns:
        {
            "segments": [...],
            "total": int,
            "dialogue_count": int,
            "narration_count": int,
            "speaker_distribution": {speaker: count, ...},
            "dialogue_ratio": float  (0-1)
        }
    """
    raw = call_llm(DIALOGUE_EXTRACT_PROMPT, f"## 小说原文\n\n{text}")
    cleaned = _clean_json(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise AppException(
            ErrorCode.LLM_PARSE_ERROR,
            f"对话分离 JSON 解析失败。LLM 原始输出片段: {raw[:200]}"
        )

    if not isinstance(data, dict):
        raise AppException(ErrorCode.LLM_PARSE_ERROR, "LLM 输出的不是 JSON 对象")

    segments_raw = data.get("segments", [])
    if not isinstance(segments_raw, list):
        raise AppException(ErrorCode.LLM_PARSE_ERROR, "segments 字段不是数组")

    # 校验每个片段
    segments = [_validate_segment(s, i + 1) for i, s in enumerate(segments_raw) if isinstance(s, dict)]

    # 统计
    dialogue_count = sum(1 for s in segments if s["type"] == "dialogue")
    narration_count = sum(1 for s in segments if s["type"] == "narration")

    # 发言者分布
    speaker_dist: dict[str, int] = {}
    for s in segments:
        if s["type"] == "dialogue" and s.get("speaker"):
            sp = s["speaker"]
            speaker_dist[sp] = speaker_dist.get(sp, 0) + 1

    total = len(segments)
    dialogue_ratio = dialogue_count / total if total > 0 else 0

    return {
        "segments": segments,
        "total": total,
        "dialogue_count": dialogue_count,
        "narration_count": narration_count,
        "speaker_distribution": speaker_dist,
        "dialogue_ratio": round(dialogue_ratio, 3),
    }
