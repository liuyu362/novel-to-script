"""
角色列表自动提取
从小说文本中识别所有出场角色，输出结构化角色信息
"""
import json
import re
from backend.llm_client import call_llm
from backend.errors import AppException, ErrorCode


CHARACTER_EXTRACT_PROMPT = """你是一位专业的文学分析师，擅长从小说文本中提取和分析角色。

## 任务
仔细阅读以下小说片段，提取所有出场角色。对每个角色，尽可能推断以下信息：

## 输出格式
**严格输出 JSON 数组，不要添加任何解释文字。** 格式如下：

```json
[
  {
    "name": "角色姓名",
    "gender": "男 / 女 / 未知",
    "age": "具体年龄或年龄段（如 28岁 / 中年 / 少年）",
    "role_type": "主角 / 配角 / 反派 / 路人",
    "description": "外貌、性格、身份的简要描述",
    "aliases": ["别名1", "别名2"],
    "first_mention": "角色首次出场的关键词或段落开头"
  }
]
```

## 提取规则
1. **完整性**：所有有台词或被提及姓名的角色都要提取
2. **推断优先**：根据上下文合理推断性别、年龄，不确定时填"未知"
3. **描述精简**：description 控制在 30 字以内
4. **别名收录**：昵称、称号、外号都放入 aliases 数组
5. **角色类型判断**：
   - 主角：叙事视角人物，出现频率最高
   - 配角：辅助推动剧情
   - 反派：与主角对立
   - 路人：仅出场一次或无台词

## 输出要求
只输出 JSON 数组，不要有任何其他文字。
"""


def _clean_json(text: str) -> str:
    """清洗 LLM 输出，提取 JSON 数组"""
    text = text.strip()
    # 去掉 markdown 代码块标记
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    # 找到 JSON 数组
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        return match.group(0)
    return text


def _validate_character(char: dict) -> dict:
    """校验并补齐角色字段"""
    defaults = {
        "name": "未知角色",
        "gender": "未知",
        "age": "未知",
        "role_type": "配角",
        "description": "",
        "aliases": [],
        "first_mention": "",
    }
    for key, default in defaults.items():
        if key not in char or char[key] is None:
            char[key] = default
    # 类型纠正
    if not isinstance(char.get("aliases"), list):
        char["aliases"] = []
    # 合法值约束
    if char["gender"] not in ("男", "女", "未知"):
        char["gender"] = "未知"
    if char["role_type"] not in ("主角", "配角", "反派", "路人"):
        char["role_type"] = "配角"
    return char


def extract_characters(text: str) -> dict:
    """从小说文本中提取角色列表

    Args:
        text: 小说原文

    Returns:
        {
            "characters": [...],
            "total": int,
            "role_distribution": {"主角": n, "配角": n, "反派": n, "路人": n}
        }
    """
    # 将小说文本作为 user prompt 传入，system prompt 由 call_llm 处理
    raw = call_llm(CHARACTER_EXTRACT_PROMPT, f"## 小说原文\n\n{text}")
    cleaned = _clean_json(raw)

    try:
        characters = json.loads(cleaned)
    except json.JSONDecodeError:
        raise AppException(
            ErrorCode.LLM_PARSE_ERROR,
            f"角色列表 JSON 解析失败。LLM 原始输出片段: {raw[:200]}"
        )

    if not isinstance(characters, list):
        raise AppException(ErrorCode.LLM_PARSE_ERROR, "LLM 输出的不是数组格式")

    # 校验每个角色
    characters = [_validate_character(c) for c in characters if isinstance(c, dict)]

    # 统计分布
    distribution = {"主角": 0, "配角": 0, "反派": 0, "路人": 0}
    for c in characters:
        t = c.get("role_type", "配角")
        if t in distribution:
            distribution[t] += 1

    return {
        "characters": characters,
        "total": len(characters),
        "role_distribution": distribution,
    }
