"""
测试被截断的 JSON 解析修复
模拟 LLM max_tokens 不足导致的输出截断场景
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.json_utils import parse_llm_json

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

# 模拟 dialogue_parse_error 日志中的真实截断场景
# 片段 55 完整，片段 56 写到一半就截断了
truncated = '''{
  "片段列表": [
    {
      "序号": 1,
      "类型": "叙述",
      "内容": "七玄武府，位于天运国国都天运城。",
      "描述": "背景介绍"
    },
    {
      "序号": 2,
      "类型": "对话",
      "发言者": "林小东",
      "内容": "铭哥，今天是七玄武府入门考核报名的日子。",
      "引号风格": "双引号",
      "语气": "轻松"
    },
    {
      "序号": 3,
      "类型": "对话",
      "发言者": "林铭",
      "内容": "刚开始报名的人很多，排队都要一两个时辰。",
      "引号风格": "双引号",
      "语气": "平静"
    },
    {
      "序号": 4,
      "类型": "叙述",
      "内容": "林小东走近树桩，看到那树桩上的拳印和斑斑血迹。",
      "描述": "动作描写"
    },
    {
      "序号": 5,
      "类型": "对话",
      "发言者": "林小东",
      "内容": "你真是够疯，铁木都被你打成这个样子。",
      "引号风格": "双引号",
      "语气": "担忧"
    },
    {
      "序号": 6,
      "类型": "叙述",
      "内容": "林铭没说话。",
      "描述": "动作描写"
    },
    {
      "序号": 7,
      "类型": "叙述",
      "内容": "林小东从怀里掏出一个布包。",
      "描述": "动作描写"
    },
    {
      "序号": 8,
      "类型": "对话",
      "发言者": "林小东",
      "内容": "铭哥，这个给你。",
      "引号风格": "双引号",
      "语气": "真诚"
    },
    {
      "序号": 9,
      "类型": "叙述",
      "内容": "林铭回头一看，是一株百年血参。",
      "描述": "动作描写"
    },
    {
      "序号": 10,
      "类型": "对话",
      "发言者": "林铭",
      "内容": "这血参我不能要。",
      "引号风格": "双引号",
      "语气": "坚定"
    },
    {
      "序号": 11,
      "类型": "叙述",
      "内容": "兄弟归兄弟，但是这血参太贵重。",
      "描述": "心理独白"
    },
    {
      "序号": 12,
      "类型": "对话",
      "发言者": "林小东",
      "内容": "这血参就是给你买的，你不用我就白买了。",
      "引号风格": "双引号",
      "语气": "真诚"
    },
    {
      "序号": 13,
      "类型": "叙述",
      "内容": "林铭沉默了一会儿，还是把血参收了起来。",
      "描述": "动作描写"
    },
    {
      "序号": 14,
      "类型": "对话",
      "发言者": "林铭",
      "内容": "好，这血参我收下了，就冲着这棵参，我也得冲破凝脉境。",
      "引号风格": "双引号",
      "语气": "坚定"
    },
    {
      "序号": 15,
      "类型": "对话",
      "'''

print("=== 测试: 被截断的 JSON（模拟 LLM max_tokens 不足）===")
try:
    result = parse_llm_json(truncated)
    check("截断 JSON 解析成功", result is not None)
    check("片段列表存在", "片段列表" in result)
    check("至少保留前14个完整片段", len(result["片段列表"]) >= 14)
    print(f"  实际保留片段数: {len(result['片段列表'])}")
except Exception as e:
    check("截断 JSON 解析成功", False)
    print(f"  错误: {e}")

# 测试2: 只有一个片段就被截断
truncated2 = '''{
  "片段列表": [
    {
      "序号": 1,
      "类型": "对话",
      "发言者": "张三",
      "内容": "你好，'''

print("\n=== 测试: 单个片段被截断 ===")
try:
    result = parse_llm_json(truncated2)
    check("单片段截断解析成功", result is not None)
    check("片段列表存在", "片段列表" in result)
except Exception as e:
    check("单片段截断解析成功", False)
    print(f"  错误: {e}")

# 测试3: 空数组截断
truncated3 = '''{
  "片段列表": ['''

print("\n=== 测试: 空数组截断 ===")
try:
    result = parse_llm_json(truncated3)
    check("空数组截断解析成功", result is not None)
    check("片段列表是空数组", result["片段列表"] == [])
except Exception as e:
    check("空数组截断解析成功", False)
    print(f"  错误: {e}")

# 测试4: 换行符 + 截断（日志中真实场景）
truncated4 = '''{
  "片段列表": [
    {
      "序号": 1,
      "类型": "叙述",
      "内容": "第一段\n第二段\n第三段",
      "描述": "背景介绍"
    },
    {
      "序号": 2,
      "类型": "对话",
      "发言者": "李四",
      "内容": "这句话里有\n换行符",
      "引号风格": "双引号",
      "语气": "正常"
    },
    {
      "序号": 3,
      "类型": "对话",
      "发言'''

print("\n=== 测试: 换行符 + 截断 ===")
try:
    result = parse_llm_json(truncated4)
    check("换行符+截断解析成功", result is not None)
    check("至少保留前2个片段", len(result["片段列表"]) >= 2)
    print(f"  实际保留片段数: {len(result['片段列表'])}")
except Exception as e:
    check("换行符+截断解析成功", False)
    print(f"  错误: {e}")

print(f"\n{'='*40}")
print(f"结果: {passed}/{passed+failed} 通过")
if failed > 0:
    print(f"失败: {failed}")
    sys.exit(1)
