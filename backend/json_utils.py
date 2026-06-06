"""
LLM JSON 输出解析工具
处理 LLM 返回的 JSON 中常见的格式问题：
- 字符串值内未转义的换行符
- 字符串值内未转义的制表符
"""
import json


def fix_json_string_newlines(json_str: str) -> str:
    """修复 JSON 字符串值中未转义的换行符。

    LLM 经常在 JSON 的字符串字段（如"内容"、"描述"）中直接输出原始换行符，
    这在标准 JSON 中是非法的。此函数将字符串值内部的换行符替换为 \\n，
    制表符替换为 \\t。
    """
    result = []
    i = 0
    in_string = False
    escape_next = False
    while i < len(json_str):
        ch = json_str[i]
        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue
        if ch == '\\':
            result.append(ch)
            escape_next = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if in_string:
            if ch == '\n':
                result.append('\\n')
            elif ch == '\r':
                if i + 1 < len(json_str) and json_str[i + 1] == '\n':
                    result.append('\\n')
                    i += 2
                    continue
                result.append('\\n')
            elif ch == '\t':
                result.append('\\t')
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1
    return ''.join(result)


def parse_llm_json(json_str: str):
    """健壮 JSON 解析：先尝试直接解析，失败则修复换行符后重试。

    Args:
        json_str: LLM 输出的 JSON 字符串（已去掉 markdown 代码块标记）

    Returns:
        解析后的 Python 对象（dict 或 list）

    Raises:
        json.JSONDecodeError: 修复后仍无法解析
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        fixed = fix_json_string_newlines(json_str)
        return json.loads(fixed)
