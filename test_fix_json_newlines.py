"""
测试 dialogue_separator 的 fix_json_string_newlines 和 parse_llm_json
验证 LLM 返回的含换行文本的 JSON 能被正确解析
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.json_utils import fix_json_string_newlines, parse_llm_json

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

print("=== 测试 1: 正常 JSON 不受影响 ===")
normal = '{"key": "value", "num": 1}'
result = parse_llm_json(normal)
check("正常 JSON 解析", result == {"key": "value", "num": 1})

print("\n=== 测试 2: 字符串值包含换行符 ===")
with_newlines = '''{
  "片段列表": [
    {
      "序号": 1,
      "类型": "对话",
      "发言者": "张三",
      "内容": "第一行对话
第二行对话
第三行对话",
      "语气": "正常"
    }
  ]
}'''
result = parse_llm_json(with_newlines)
check("含换行 JSON 解析成功", result is not None)
check("片段列表长度", len(result["片段列表"]) == 1)
check("内容保留完整", result["片段列表"][0]["内容"] == "第一行对话\n第二行对话\n第三行对话")

print("\n=== 测试 3: 多个片段含换行 ===")
multi = '''{
  "片段列表": [
    {
      "序号": 1,
      "类型": "对话",
      "发言者": "李四",
      "内容": "他说你好
好久不见",
      "语气": "平静"
    },
    {
      "序号": 2,
      "类型": "叙述",
      "内容": "房间里很安静
只有窗外的风声",
      "描述": "环境描写"
    }
  ]
}'''
result = parse_llm_json(multi)
check("多片段解析成功", result is not None)
check("片段数=2", len(result["片段列表"]) == 2)
check("对话内容", "好久不见" in result["片段列表"][0]["内容"])
check("叙述内容", "窗外的风声" in result["片段列表"][1]["内容"])

print("\n=== 测试 4: 特殊字符混合 ===")
special = '''{
  "片段列表": [
    {
      "序号": 1,
      "类型": "对话",
      "发言者": "王五",
      "内容": "带\\"引号\\"的文字
还有换行
以及\\t制表符",
      "语气": "激动"
    }
  ]
}'''
result = parse_llm_json(special)
check("特殊字符解析成功", result is not None)
check("内容包含换行", "\\n" in result["片段列表"][0]["内容"] or "\n" in result["片段列表"][0]["内容"])

print("\n=== 测试 5: 空字符串 ===")
check("空字符串", fix_json_string_newlines("") == "")

print("\n=== 测试 6: 没有换行的字符串 ===")
clean = '{"key": "hello world"}'
check("无换行字符串不变", fix_json_string_newlines(clean) == clean)

print(f"\n{'='*40}")
print(f"结果: {passed}/{passed+failed} 通过")
if failed > 0:
    print(f"失败: {failed}")
    sys.exit(1)
