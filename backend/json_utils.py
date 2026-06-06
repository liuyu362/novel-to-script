"""
LLM JSON 输出解析工具
处理 LLM 返回的 JSON 中常见的格式问题：
- 字符串值内未转义的换行符/制表符
- 数组内误写键值对（如 [ "key": value ] 应改为 { "key": value }）
- 字符串值内未转义的 ASCII 双引号
- 中文引号（"" '' ）替换为转义形式
"""
import json
import os
import re
import datetime


_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def _write_debug_log(step: str, json_str: str, error: str = ""):
    """将解析失败的原始 JSON 写入日志文件以便调试。"""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        fpath = os.path.join(_LOG_DIR, f"json_parse_error_{ts}.txt")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"Step: {step}\n")
            if error:
                f.write(f"Error: {error}\n")
            f.write("=" * 60 + "\n")
            f.write(f"Length: {len(json_str)} chars\n")
            f.write("=" * 60 + "\n")
            f.write(json_str)
        return fpath
    except Exception:
        return None


def fix_json_string_newlines(json_str: str) -> str:
    """修复 JSON 字符串值中未转义的换行符和特殊字符。

    LLM 经常在 JSON 的字符串字段（如"内容"、"描述"）中直接输出原始换行符，
    这在标准 JSON 中是非法的。此函数将字符串值内部的换行符替换为 \\n，
    制表符替换为 \\t，并将字符串内的未转义 ASCII 双引号转义。
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
            elif ch == '\b':
                result.append('\\b')
            elif ch == '\f':
                result.append('\\f')
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1
    return ''.join(result)


def fix_chinese_quotes_in_json(json_str: str) -> str:
    """将 JSON 字符串值内的中文引号替换为转义形式。

    LLM 有时在 JSON 字符串值中输出中文引号 "" ''，
    这些字符在 JSON 中虽不直接导致解析失败，但如果与 ASCII 引号混用
    可能引起问题。此函数在字符串内部将它们替换。
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
            if ch == '\u201c':  # "
                result.append('\\"')
            elif ch == '\u201d':  # "
                result.append('\\"')
            elif ch == '\u2018':  # '
                result.append("'")
            elif ch == '\u2019':  # '
                result.append("'")
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


def _try_parse_with_repair(json_str: str, label: str) -> tuple:
    """尝试解析 JSON，如果失败在错误位置附近截断重试。"""
    try:
        return json.loads(json_str), None
    except json.JSONDecodeError as e:
        # 尝试在错误位置截断，看是否 JSON 中混入了非 JSON 文本
        pos = e.pos
        if pos > 0:
            # 尝试去掉错误行之后的内容，用 } 或 ] 闭合
            truncated = json_str[:pos]
            # 计算未闭合的括号
            open_braces = truncated.count('{') - truncated.count('}')
            open_brackets = truncated.count('[') - truncated.count(']')
            suffix = '}' * open_braces + ']' * open_brackets
            try:
                return json.loads(truncated + suffix), f"{label}+truncate"
            except json.JSONDecodeError:
                pass
        return None, str(e)


def parse_llm_json(json_str: str):
    """健壮 JSON 解析：依次尝试多种修复策略。

    修复链（按顺序）：
    1. 直接解析
    2. 修复字符串内特殊字符（换行/制表/退格）
    3. 修复中文引号
    4. 修复数组误写为对象
    5. 修复特殊字符 + 数组→对象
    6. 修复特殊字符 + 中文引号 + 数组→对象
    7. 截断修复：在错误位置截断并闭合括号

    Args:
        json_str: LLM 输出的 JSON 字符串（已去掉 markdown 代码块标记）

    Returns:
        解析后的 Python 对象（dict 或 list）

    Raises:
        json.JSONDecodeError: 所有修复策略均失败
    """
    last_error = ""

    # 策略1: 直接解析
    result, err = _try_parse_with_repair(json_str, "direct")
    if result is not None:
        return result
    if err:
        last_error = err

    # 策略2: 修复特殊字符
    fixed = fix_json_string_newlines(json_str)
    result, err = _try_parse_with_repair(fixed, "fix_newlines")
    if result is not None:
        return result
    if err:
        last_error = err

    # 策略3: 修复中文引号
    fixed = fix_chinese_quotes_in_json(json_str)
    result, err = _try_parse_with_repair(fixed, "fix_chinese_quotes")
    if result is not None:
        return result
    if err:
        last_error = err

    # 策略4: 修复数组误写为对象
    fixed = fix_array_as_object(json_str)
    result, err = _try_parse_with_repair(fixed, "fix_array_as_object")
    if result is not None:
        return result
    if err:
        last_error = err

    # 策略5: 特殊字符 + 数组→对象
    fixed = fix_json_string_newlines(json_str)
    fixed = fix_array_as_object(fixed)
    result, err = _try_parse_with_repair(fixed, "fix_newlines+array")
    if result is not None:
        return result
    if err:
        last_error = err

    # 策略6: 全组合（特殊字符 + 中文引号 + 数组→对象）
    fixed = fix_json_string_newlines(json_str)
    fixed = fix_chinese_quotes_in_json(fixed)
    fixed = fix_array_as_object(fixed)
    result, err = _try_parse_with_repair(fixed, "fix_all")
    if result is not None:
        return result
    if err:
        last_error = err

    # 策略7: 截断修复——在错误位置截断后闭合括号（兜底）
    result, err = _try_parse_with_repair(fixed, "truncate")
    if result is not None:
        return result

    # 全部失败：写日志
    _write_debug_log("ALL_FAILED", json_str, last_error)

    raise json.JSONDecodeError(
        f"All 7 repair strategies failed. Last error: {last_error}",
        json_str, 0
    )
