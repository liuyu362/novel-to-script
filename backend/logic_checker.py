"""
逻辑矛盾检测模块
对生成剧本进行四类逻辑问题检测：
- 角色一致性：角色无故消失/出现、前后描述矛盾
- 场景连续性：场景间缺少过渡、地点跳跃不合理
- 时间线：时间顺序混乱、跨度过大无交代
- 情节漏洞：因果关系断裂、人物行为逻辑矛盾
"""
import json
import re
from backend.llm_client import call_llm

LOGIC_CHECK_SYSTEM = """你是一名资深剧本编辑，专精于逻辑矛盾检测。你的任务是仔细阅读给出的剧本YAML和小说原文，检测以下四类问题：

1. **角色一致性 (character_consistency)**：
   - 角色在某场景出现后，后续场景无故消失（无退场交代）
   - 角色前后描述矛盾（如年龄、身份、关系变化但未说明原因）
   - 角色行为与其设定不符

2. **场景连续性 (scene_continuity)**：
   - 连续两个场景之间地点跳跃过大，缺少过渡说明
   - 同一场景内时间/环境前后不一致
   - 场景切换缺少转场逻辑

3. **时间线 (timeline)**：
   - 事件发生的先后顺序存在矛盾
   - 时间跨度过大但缺少"若干天后"等过渡交代
   - 同时发生的事件在不同场景中时间标注冲突

4. **情节漏洞 (plot_hole)**：
   - 关键信息在前文已揭示，后文角色却"不知道"
   - 人物动机与行为存在明显矛盾
   - 因果关系断裂（前因无后果，或后果无前因）

## 输出格式

以 JSON 格式返回，包含一个 issues 数组：

```json
{
  "issues": [
    {
      "type": "character_consistency",
      "severity": "critical",
      "scene_ref": "Scene_1",
      "description": "角色张三在Scene_1中出场，但后续Scene_2至Scene_5均未交代其去向",
      "suggestion": "建议在Scene_2开头添加一句\"张三已先行离开\"",
      "involved": ["张三"]
    }
  ],
  "summary": {
    "total": 5,
    "critical": 2,
    "warning": 2,
    "info": 1
  }
}
```

**severity 等级说明**：
- critical：严重影响剧本逻辑，必须修复
- warning：存在明显逻辑瑕疵，建议修复
- info：轻微不一致，可选择性修复

**规则**：
- 每条 issue 必须包含 type、severity、description、suggestion 字段
- scene_ref 和 involved 可选，但有助于定位问题时必须提供
- 如果未发现问题，返回空数组 `"issues": []`，summary 各字段为 0
- 只输出 JSON，不要输出其他内容"""


def check_logic(script_yaml: str, original_text: str, title: str = "") -> dict:
    """检测剧本中的逻辑矛盾

    Args:
        script_yaml: 生成的剧本 YAML 文本
        original_text: 小说原文（用作参考基准）
        title: 作品标题

    Returns:
        {
            "issues": [...],
            "summary": {"total": N, "critical": N, "warning": N, "info": N},
            "raw_response": "..."
        }
    """
    user_prompt = f"""请检测以下剧本中的逻辑矛盾。

## 作品标题
{title or '未命名'}

## 小说原文（参考基准）
{original_text[:3000]}

## 生成的剧本
{script_yaml[:5000]}

请分析剧本与原文之间、剧本内部是否存在逻辑矛盾，以 JSON 格式返回检测结果。"""

    raw = call_llm(LOGIC_CHECK_SYSTEM, user_prompt)

    # 尝试从 LLM 回复中提取 JSON
    issues = []
    summary = {"total": 0, "critical": 0, "warning": 0, "info": 0}

    try:
        # 尝试直接解析
        data = json.loads(raw)
        issues = data.get("issues", [])
        summary = data.get("summary", {"total": 0, "critical": 0, "warning": 0, "info": 0})
    except json.JSONDecodeError:
        # 尝试从 markdown 代码块中提取
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if match:
            try:
                data = json.loads(match.group(1))
                issues = data.get("issues", [])
                summary = data.get("summary", {"total": 0, "critical": 0, "warning": 0, "info": 0})
            except json.JSONDecodeError:
                # 尝试找到 JSON 对象
                match2 = re.search(r'\{[\s\S]*"issues"[\s\S]*\}', raw)
                if match2:
                    try:
                        data = json.loads(match2.group(0))
                        issues = data.get("issues", [])
                        summary = data.get("summary", {"total": 0, "critical": 0, "warning": 0, "info": 0})
                    except json.JSONDecodeError:
                        pass

    # 兜底：根据 issues 计算 summary
    if issues and summary.get("total", 0) == 0:
        critical = sum(1 for i in issues if i.get("severity") == "critical")
        warning = sum(1 for i in issues if i.get("severity") == "warning")
        info = sum(1 for i in issues if i.get("severity") == "info")
        summary = {
            "total": len(issues),
            "critical": critical,
            "warning": warning,
            "info": info,
        }

    # 验证每条 issue 必需字段
    validated_issues = []
    for iss in issues:
        if not isinstance(iss, dict):
            continue
        if "type" not in iss or "description" not in iss:
            continue
        validated_issues.append({
            "type": iss.get("type", "unknown"),
            "severity": iss.get("severity", "info"),
            "scene_ref": iss.get("scene_ref", ""),
            "description": iss.get("description", ""),
            "suggestion": iss.get("suggestion", ""),
            "involved": iss.get("involved", []),
        })

    return {
        "issues": validated_issues,
        "summary": summary,
        "raw_response": raw,
    }
