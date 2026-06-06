"""
LLM JSON 输出解析工具
处理 LLM 返回的 JSON 中常见的格式问题：
- 字符串值内未转义的换行符/制表符
- 数组内误写键值对（如 [ "key": value ] 应改为 { "key": value }）
"""
import json
import re


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


def _contains_kv_in_array(arr_content: str) -> bool:
    """检测数组内容是否直接包含键值对模式（如 "key": value）。

    跳过嵌套的子数组 [...] 和子对象 {...}，只检查当前层。
    例如 [{"a":1}, {"b":2}] 不包含直接键值对（子对象不算），
    而 ["序号":1, "类型":"校武"] 包含直接键值对。
    """
    i = 0
    in_string = False
    escape = False
    depth = 0  # 嵌套深度：遇到 { 或 [ 加1，遇到 } 或 ] 减1
    while i < len(arr_content):
        ch = arr_content[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == '\\':
            escape = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            i += 1
            continue
        if not in_string:
            if ch in '{[':
                depth += 1
                i += 1
                continue
            if ch in '}]':
                depth -= 1
                i += 1
                continue
            if depth == 0 and ch == ':':
                # 只在顶层检测冒号
                j = i - 1
                while j >= 0 and arr_content[j] in ' \t\n\r':
                    j -= 1
                if j >= 0 and arr_content[j] == '"':
                    return True
        i += 1
    return False


def fix_array_as_object(json_str: str) -> str:
    """将 JSON 中误写成数组的对象修正。

    LLM 有时会输出 {"key": [ "序号":1, "类型":"校武" ]}
    这种格式——把本该是对象 {} 的内容写成了数组 []。
    此函数检测 [...] 内部包含键值对的情况，将 [ 和 ] 替换为 { 和 }。

    注意：需要确保不误伤正常的数组。只处理包含键值对的 [...] 。
    """
    # 使用正则匹配所有顶层或嵌套的 [... ] 对
    # 从内到外处理嵌套
    def _fix_inner(s: str) -> str:
        # 匹配 [... ] 对，从最内层开始
        result = []
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == '"':
                # 跳过字符串
                result.append(ch)
                i += 1
                while i < len(s):
                    if s[i] == '\\':
                        result.append(s[i])
                        i += 1
                        if i < len(s):
                            result.append(s[i])
                            i += 1
                        continue
                    if s[i] == '"':
                        result.append(s[i])
                        i += 1
                        break
                    result.append(s[i])
                    i += 1
                continue
            if ch == '[':
                # 找到匹配的 ]
                depth = 1
                j = i + 1
                in_str = False
                esc = False
                while j < len(s) and depth > 0:
                    c2 = s[j]
                    if esc:
                        esc = False
                        j += 1
                        continue
                    if c2 == '\\':
                        esc = True
                        j += 1
                        continue
                    if c2 == '"':
                        in_str = not in_str
                        j += 1
                        continue
                    if not in_str:
                        if c2 == '[':
                            depth += 1
                        elif c2 == ']':
                            depth -= 1
                    j += 1
                if depth == 0:
                    inner = s[i + 1:j - 1]
                    # 递归处理嵌套
                    inner_fixed = _fix_inner(inner)
                    if _contains_kv_in_array(inner_fixed):
                        # 这是误写的对象，用 {} 替换 []
                        result.append('{')
                        result.append(inner_fixed)
                        result.append('}')
                    else:
                        result.append('[')
                        result.append(inner_fixed)
                        result.append(']')
                    i = j
                    continue
            result.append(ch)
            i += 1
        return ''.join(result)
    return _fix_inner(json_str)


def parse_llm_json(json_str: str):
    """健壮 JSON 解析：依次尝试多种修复策略。

    修复链：
    1. 直接解析
    2. 修复字符串内换行符后解析
    3. 修复数组误写为对象后解析
    4. 组合修复（换行符 + 数组→对象）

    Args:
        json_str: LLM 输出的 JSON 字符串（已去掉 markdown 代码块标记）

    Returns:
        解析后的 Python 对象（dict 或 list）

    Raises:
        json.JSONDecodeError: 所有修复策略均失败
    """
    # 策略1: 直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 策略2: 修复换行符
    try:
        fixed = fix_json_string_newlines(json_str)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 策略3: 修复数组误写为对象
    try:
        fixed = fix_array_as_object(json_str)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 策略4: 组合修复（换行符 + 数组→对象）
    fixed = fix_json_string_newlines(json_str)
    fixed = fix_array_as_object(fixed)
    return json.loads(fixed)
