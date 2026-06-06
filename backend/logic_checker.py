"""
逻辑矛盾检测模块（全中文字段名）
对生成剧本进行四类逻辑问题检测：
- 角色一致性：角色无故消失/出现、前后描述矛盾
- 场景连续性：场景间缺少过渡、地点跳跃不合理
- 时间线：时间顺序混乱、跨度过大无交代
- 情节漏洞：因果关系断裂、人物行为逻辑矛盾
"""
import json
import os
import re
import datetime
from backend.llm_client import call_llm
from backend.json_utils import parse_llm_json


def _write_debug_log(step: str, raw: str):
    """写入调试日志"""
    try:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_path = os.path.join(log_dir, f"logic_parse_error_{ts}.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Step: {step}\n")
            f.write(f"Length: {len(raw)} chars\n")
            f.write("=" * 60 + "\n")
            f.write(raw)
        return log_path
    except Exception:
        return None

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

以 JSON 格式返回，包含一个 问题列表 数组：

```json
{
  "问题列表": [
    {
      "类型": "character_consistency",
      "严重程度": "critical",
      "关联场景": "Scene_1",
      "描述": "角色张三在Scene_1中出场，但后续Scene_2至Scene_5均未交代其去向",
      "建议": "建议在Scene_2开头添加一句\"张三已先行离开\"",
      "涉及角色": ["张三"],
      "修复操作": {
        "查找文本": "Scene_2:",
        "替换为": "Scene_2:\\n  说明: 张三已先行离开\\nScene_2:"
      }
    }
  ],
  "汇总": {
    "总数": 5,
    "严重": 2,
    "警告": 2,
    "提示": 1
  }
}
```

**严重程度 等级说明**：
- critical：严重影响剧本逻辑，必须修复
- warning：存在明显逻辑瑕疵，建议修复
- info：轻微不一致，可选择性修复

**修复操作 说明**：
- `修复操作` 是可选字段，为每条问题提供可直接在 YAML 中执行的查找替换方案
- `查找文本`：在剧本 YAML 中定位问题位置的唯一文本片段（建议5-30字，能唯一匹配到问题行的上下文）
- `替换为`：修复后的完整文本（将查找文本替换为修正版本，保持 YAML 结构不变）
- 如果不能给出精确的查找替换方案，省略 `修复操作` 字段

**规则**：
- 每条 issue 必须包含 类型、严重程度、描述、建议 字段
- 关联场景 和 涉及角色 可选，但有助于定位问题时必须提供
- 如果未发现问题，返回空数组 `"问题列表": []`，汇总 各字段为 0
- 只输出 JSON，不要输出其他内容"""


def check_logic(script_yaml: str, original_text: str, title: str = "") -> dict:
    """检测剧本中的逻辑矛盾

    Args:
        script_yaml: 生成的剧本 YAML 文本
        original_text: 小说原文（用作参考基准）
        title: 作品标题

    Returns:
        {
            "问题列表": [...],
            "汇总": {"总数": N, "严重": N, "警告": N, "提示": N},
            "原始响应": "..."
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
    summary = {"总数": 0, "严重": 0, "警告": 0, "提示": 0}

    try:
        # 尝试直接解析
        data = parse_llm_json(raw)
        issues = data.get("问题列表", [])
        summary = data.get("汇总", {"总数": 0, "严重": 0, "警告": 0, "提示": 0})
    except json.JSONDecodeError:
        _write_debug_log("logic_checker", raw)
        # 尝试从 markdown 代码块中提取
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if match:
            try:
                data = parse_llm_json(match.group(1))
                issues = data.get("问题列表", [])
                summary = data.get("汇总", {"总数": 0, "严重": 0, "警告": 0, "提示": 0})
            except json.JSONDecodeError:
                # 尝试找到 JSON 对象
                match2 = re.search(r'\{[\s\S]*"问题列表"[\s\S]*\}', raw)
                if match2:
                    try:
                        data = parse_llm_json(match2.group(0))
                        issues = data.get("问题列表", [])
                        summary = data.get("汇总", {"总数": 0, "严重": 0, "警告": 0, "提示": 0})
                    except json.JSONDecodeError:
                        pass

    # 兜底：根据 issues 计算 汇总
    if issues and summary.get("总数", 0) == 0:
        critical = sum(1 for i in issues if i.get("严重程度") == "critical")
        warning = sum(1 for i in issues if i.get("严重程度") == "warning")
        info = sum(1 for i in issues if i.get("严重程度") == "info")
        summary = {
            "总数": len(issues),
            "严重": critical,
            "警告": warning,
            "提示": info,
        }

    # 验证每条 issue 必需字段
    validated_issues = []
    for iss in issues:
        if not isinstance(iss, dict):
            continue
        if "类型" not in iss or "描述" not in iss:
            continue
        validated_issues.append({
            "类型": iss.get("类型", "unknown"),
            "严重程度": iss.get("严重程度", "info"),
            "关联场景": iss.get("关联场景", ""),
            "描述": iss.get("描述", ""),
            "建议": iss.get("建议", ""),
            "涉及角色": iss.get("涉及角色", []),
            "修复操作": iss.get("修复操作", None),
        })

    return {
        "问题列表": validated_issues,
        "汇总": summary,
        "原始响应": raw,
    }
