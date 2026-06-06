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


def _find_scene_in_yaml(script_yaml: str, scene_name: str) -> str:
    """在 YAML 中搜索场景名，返回找到的实际子串（用于更新查找文本）

    匹配策略（按顺序尝试）：
    1. 精确匹配场景名
    2. 去掉前后空格后再匹配
    3. 场景名作为行首（如 "铁木练拳" 匹配 "铁木练拳\n   人物："）
    4. 场景名前后加冒号（如 "第一场：铁木练拳"）
    """
    if not scene_name:
        return ""

    # 策略1：精确子串匹配
    if scene_name in script_yaml:
        return scene_name

    # 策略2：去掉前后空格后匹配
    scene_clean = scene_name.strip()
    idx = script_yaml.find(scene_clean)
    if idx >= 0:
        return scene_clean

    # 策略3：场景名在 YAML 中作为独立行（场景头），尝试匹配行首
    # 典型格式："铁木练拳\n    人物：..." 或 "第一场：铁木练拳\n    人物：..."
    lines = script_yaml.split('\n')
    for line in lines:
        line_stripped = line.strip()
        # 场景头行：不含冒号后面跟字段的，通常是纯场景名或以"第X场"开头
        if line_stripped == scene_clean:
            return line_stripped
        if line_stripped.startswith(scene_clean):
            return line_stripped
        # 尝试匹配"第X场：场景名"格式
        if scene_clean in line_stripped:
            return line_stripped

    # 策略4：尝试在场景名前后加冒号再匹配
    if '：' not in scene_clean:
        # 尝试 "场景名：" 格式
        pattern = scene_clean + '：'
        if pattern in script_yaml:
            return pattern
        # 尝试 "：场景名" 格式（从关联场景字段提取）
        # 关联场景可能是 "第一场：铁木练拳"，实际 YAML 里是 "铁木练拳"
        # 提取冒号后面的部分
        if '：' in scene_name:
            name_only = scene_name.split('：', 1)[1].strip()
            if name_only in script_yaml:
                return name_only

    return ""


def _try_fix_find_text(script_yaml: str, find_text: str, scene_name: str) -> str:
    """尝试修复查找文本，返回修复后的文本；如果无法修复返回空字符串"""

    # 策略1：直接精确匹配
    if find_text and find_text in script_yaml:
        return find_text

    # 策略2：去掉前后空格/换行
    if find_text:
        cleaned = find_text.strip()
        if cleaned in script_yaml:
            return cleaned

    # 策略3：从关联场景字段在 YAML 中找实际场景名
    actual_scene = _find_scene_in_yaml(script_yaml, scene_name)
    if actual_scene:
        # 返回场景名作为查找文本（至少能定位到场景头）
        return actual_scene

    # 策略4：尝试在查找文本中去掉多余字符（如 LLM 加了多余标点）
    if find_text:
        # 去掉末尾的冒号、句号等
        stripped = re.sub(r'[：:，,。\.、\s]+$', '', find_text.strip())
        if stripped in script_yaml:
            return stripped
        # 去掉开头的"第一场："等前缀，只保留场景名
        stripped2 = re.sub(r'^第[一二三四五六七八九十\d]+场[：:]\s*', '', find_text.strip())
        if stripped2 in script_yaml:
            return stripped2

    return ""


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

## 剧本 YAML 格式说明

剧本 YAML 的典型格式如下（场景名均为中文，"第X场："开头或纯场景名）：

```
剧名：某某剧本
作者：AI助手

铁木练拳
    人物：张三，李四
    时间：白天
    地点：大周山山脚林间草地
    内/外：外
    天气：晴
    摘要：两人在草地练拳
    正文：|1|
      张三：今天天气真好。
      李四：是啊，好久没出来了。

咖啡馆内
    人物：张三
    时间：傍晚
    ...
```

注意：
- 场景名格式可能有两种：纯场景名（如"铁木练拳"）或"第X场：场景名"（如"第二场：咖啡馆内"）
- 所有场景名都是中文，不要使用"Scene_1"等英文格式
- 场景名后面紧跟换行和缩进的字段（人物、时间等）

## 输出格式

以 JSON 格式返回，包含一个 问题列表 数组：

```json
{
  "问题列表": [
    {
      "类型": "character_consistency",
      "严重程度": "critical",
      "关联场景": "铁木练拳",
      "描述": "张三在"铁木练拳"场景中出现，但后续"咖啡馆内"场景突然消失且无退场交代",
      "建议": "建议在"咖啡馆内"场景开头添加"张三告辞离开"的过渡说明",
      "涉及角色": ["张三"],
      "修复操作": {
        "查找文本": "咖啡馆内",
        "替换为": "咖啡馆内\\n    说明：张三已告辞离开"
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

**修复操作 关键规则（必须严格遵守）**：

1. `修复操作` 是可选字段，只有当你能精确定位并给出可执行的查找替换方案时才包含此字段。

2. `查找文本` 的严格要求（违反任何一条都必须省略 `修复操作`）：
   - 必须从上面"生成的剧本"YAML 中**原样复制**一段连续文本，一个字都不能改、不能加、不能减、不能换标点
   - 建议长度 2~50 个字符，必须能在 YAML 中找到完全匹配的子串
   - 禁止自己概括、改写、翻译场景名（如把"铁木练拳"写成"Scene_1"或"练拳场景"都是错误的）
   - 写完后必须验证：`查找文本` 作为子串能否在"生成的剧本"YAML 中找到完全匹配

3. `替换为` 的严格要求：
   - 将 `查找文本` 替换为修复后的文本，保持 YAML 缩进格式不变
   - 新增行的缩进必须与上下文一致（场景正文用4个空格缩进，字段用4个空格缩进）

4. **自检步骤（输出前必须执行）**：
   - 步骤1：在"生成的剧本"YAML 中搜索 `查找文本`，确认能找到完全匹配
   - 步骤2：如果找不到，删除 `修复操作` 字段，不要瞎编
   - 步骤3：确认 `关联场景` 的值与 YAML 中的某个场景名完全一致

**规则**：
- 每条 issue 必须包含 类型、严重程度、描述、建议 字段
- `关联场景`：填写中文场景名，格式与 YAML 中完全一致（如"铁木练拳"或"第二场：咖啡馆内"），不要写"Scene_2"
- `涉及角色` 可选，但有助于定位问题时必须提供
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

请分析剧本与原文之间、剧本内部是否存在逻辑矛盾，以 JSON 格式返回检测结果。

重要提醒：
- 生成"修复操作"时，"查找文本"必须从上面"生成的剧本"中逐字复制，不能自己改写。
- 输出前请验证："查找文本"能否在"生成的剧本"中找到完全匹配的子串。如果找不到，省略"修复操作"。
- "关联场景"必须与"生成的剧本"中的场景名完全一致（中文，可能是纯场景名如"铁木练拳"，也可能是"第X场：场景名"格式）。"""

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

    # 后端二次验证：修复查找文本，使其能在 YAML 中找到匹配
    validated_issues = []
    for iss in issues:
        if not isinstance(iss, dict):
            continue
        if "类型" not in iss or "描述" not in iss:
            continue

        fix_op = iss.get("修复操作")
        scene_name = iss.get("关联场景", "")

        if fix_op and isinstance(fix_op, dict):
            find_text = fix_op.get("查找文本", "")
            replace_text = fix_op.get("替换为", "")

            # 尝试修复查找文本
            fixed_find = _try_fix_find_text(script_yaml, find_text, scene_name)

            if fixed_find and fixed_find in script_yaml:
                # 修复成功，更新查找文本
                fix_op = {
                    "查找文本": fixed_find,
                    "替换为": replace_text or find_text,
                }
            else:
                # 无法修复，删除修复操作
                fix_op = None

        validated_issues.append({
            "类型": iss.get("类型", "unknown"),
            "严重程度": iss.get("严重程度", "info"),
            "关联场景": scene_name,
            "描述": iss.get("描述", ""),
            "建议": iss.get("建议", ""),
            "涉及角色": iss.get("涉及角色", []),
            "修复操作": fix_op,
        })

    # 根据验证后的问题列表重新计算汇总
    if validated_issues:
        critical = sum(1 for i in validated_issues if i.get("严重程度") == "critical")
        warning = sum(1 for i in validated_issues if i.get("严重程度") == "warning")
        info = sum(1 for i in validated_issues if i.get("严重程度") == "info")
        summary = {
            "总数": len(validated_issues),
            "严重": critical,
            "警告": warning,
            "提示": info,
        }

    return {
        "问题列表": validated_issues,
        "汇总": summary,
        "原始响应": raw,
    }
