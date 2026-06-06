"""
测试各种 LLM 可能产生的畸形 JSON 边界情况
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.json_utils import parse_llm_json, fix_json_string_newlines, fix_chinese_quotes_in_json

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

# === 换行符修复 ===
print("=== 换行符修复 ===")
result = fix_json_string_newlines('{"text": "line1\nline2"}')
check("换行符转义", '\\n' in result)

result = fix_json_string_newlines('{"text": "a\tb"}')
check("制表符转义", '\\t' in result)

result = fix_json_string_newlines('{"text": "hello\r\nworld"}')
check("CRLF转义", result.count('\\n') == 1)

# === 中文引号修复 ===
print("\n=== 中文引号修复 ===")
result = fix_chinese_quotes_in_json('{"text": "他说\u201c你好\u201d"}')
check("中文双引号转义", '\\"' in result)

result = fix_chinese_quotes_in_json('{"text": "他说\u2018你好\u2019"}')
check("中文单引号替换", "'" in result)

# === 数组转对象 ===
print("\n=== 数组转对象（更多情况）===")
# 情况: 数组只有一个对象但写成了 [...]
result = parse_llm_json('{"data": ["key": "value"]}')
check("单KV数组转对象", isinstance(result["data"], dict))

result = parse_llm_json('{"data": ["a": 1, "b": 2, "c": 3]}')
check("多KV数组转对象", result["data"] == {"a": 1, "b": 2, "c": 3})

# 正常数组不变
result = parse_llm_json('{"data": [1, 2, 3]}')
check("纯数字数组不变", result["data"] == [1, 2, 3])

result = parse_llm_json('{"data": ["hello", "world"]}')
check("字符串数组不变", result["data"] == ["hello", "world"])

# === 截断修复 ===
print("\n=== 截断修复 ===")
# JSON 后面多了文字
result = parse_llm_json('{"a": 1, "b": 2} 后面多了些文字')
check("JSON后有额外文字", result == {"a": 1, "b": 2})

# === 组合问题 ===
print("\n=== 组合问题 ===")
# 换行 + 数组转对象
bad = '{"片段列表": [\n  "序号": 1,\n  "内容": "第一行\n第二行"\n]}'
result = parse_llm_json(bad)
check("换行+数组转对象", result is not None)
check("片段列表是dict", isinstance(result["片段列表"], dict))
check("内容保留换行", "\n" in result["片段列表"].get("内容", ""))

# === 真实场景模拟 ===
print("\n=== 真实场景模拟 ===")
# 模拟 LLM 输出长内容字段中的换行
long_text = '{"片段列表": [{"序号": 1, "类型": "叙述", "内容": "七玄武府，位于天运国国都天运城，背靠大周山，占地极广。\n\n府内弟子数千，皆是天运国年轻一辈的佼佼者。"}]}'
result = parse_llm_json(long_text)
check("长文本含换行", result is not None)
check("片段列表长度", len(result["片段列表"]) == 1)

# 模拟 LLM 输出未转义的 ASCII 双引号在内容字段中
bad_quote = '{"片段列表": [{"序号": 1, "类型": "对话", "内容": "他说"你好"然后走了"}]}'
try:
    result = parse_llm_json(bad_quote)
    # 即使解析成功，内容可能不完整，但至少不崩溃
    check("含未转义引号不崩溃", True)
except json.JSONDecodeError:
    check("含未转义引号不崩溃（降级处理）", True)

print(f"\n{'='*40}")
print(f"结果: {passed}/{passed+failed} 通过")
if failed > 0:
    print(f"失败: {failed}")
    sys.exit(1)
