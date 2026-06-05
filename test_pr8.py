"""PR8 验证器测试脚本"""
import requests
import json

# 测试数据：故意包含各种错误
test_yaml = """meta:
  title: 测试剧本
  version: invalid_version
characters:
  - name: 张三
    gender: 外星人
  - no_name_here: true
scenes:
  - name: 第一幕
    acts:
      - type: singing
        content: 角色开始唱歌
      - type: dialogue
        content: Hello world
        character: ""
      - content: 没有 type 的 act"""

def test_validate():
    print("=" * 60)
    print("测试 1: POST /api/validate（错误 YAML）")
    print("=" * 60)
    resp = requests.post(
        "http://127.0.0.1:8000/api/validate",
        json={"yaml_text": test_yaml, "source_title": "测试作品"},
    )
    data = resp.json()
    print(f"状态码: {resp.status_code}")
    print(f"code: {data['code']}")
    print(f"message: {data['message']}")
    
    if data.get("data", {}).get("validation"):
        val = data["data"]["validation"]
        print(f"\n📊 验证报告:")
        print(f"  通过: {val['is_valid']}")
        print(f"  问题数: {val['total_issues']}")
        print(f"  修复数: {val['total_fixes']}")
        print(f"\n  修复记录:")
        for f in val["fixes_applied"]:
            print(f"    🔧 {f}")
        print(f"\n  问题列表:")
        for i in val["issues"]:
            icon = {"error": "❌", "warning": "⚠️", "fixed": "✅"}.get(i["severity"], "•")
            print(f"    {icon} [{i['field']}] {i['message']}")
        
        if data["data"].get("script_stats"):
            print(f"\n📈 统计: {data['data']['script_stats']}")

def test_valid_yaml():
    print("\n" + "=" * 60)
    print("测试 2: POST /api/validate（正常 YAML）")
    print("=" * 60)
    valid_yaml = """meta:
  title: 正常剧本
  version: movie
characters:
  - id: 1
    name: 李雷
    gender: 男
    role_type: 主角
    description: 勇敢的年轻人
  - id: 2
    name: 韩梅梅
    gender: 女
    role_type: 配角
    description: 李雷的朋友
scenes:
  - id: 1
    name: 开场
    location: 教室
    time: 上午
    weather: 晴
    acts:
      - type: action
        content: 李雷走进教室
        character: 李雷
        emotion: 平静
      - type: dialogue
        content: 早上好，韩梅梅
        character: 李雷
        emotion: 喜悦"""
    
    resp = requests.post(
        "http://127.0.0.1:8000/api/validate",
        json={"yaml_text": valid_yaml},
    )
    data = resp.json()
    print(f"code: {data['code']}, message: {data['message']}")
    if data.get("data", {}).get("validation"):
        val = data["data"]["validation"]
        print(f"通过: {val['is_valid']}, 修复数: {val['total_fixes']}")
        if val['fixes_applied']:
            for f in val['fixes_applied']:
                print(f"  🔧 {f}")

if __name__ == "__main__":
    test_validate()
    test_valid_yaml()
