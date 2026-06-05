"""PR8 验证器直接测试（不通过 HTTP）"""
import sys
sys.path.insert(0, r"F:\七牛云议题\novel-to-script")

from backend.yaml_parser import parse_yaml_to_script, script_to_yaml
from backend.yaml_validator import validate_and_fix_script, report_to_dict

print("=" * 60)
print("测试 1: 错误 YAML（各种问题）")
print("=" * 60)

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

try:
    script = parse_yaml_to_script(test_yaml, source_title="测试作品")
    fixed_script, report = validate_and_fix_script(script)
    val = report_to_dict(report)
    
    print(f"\n通过: {val['is_valid']}")
    print(f"问题数: {val['total_issues']}")
    print(f"修复数: {val['total_fixes']}")
    print(f"\n修复记录:")
    for f in val['fixes_applied']:
        print(f"  [FIX] {f}")
    print(f"\n问题列表:")
    for i in val['issues']:
        icon = {"error": "ERROR", "warning": "WARN", "fixed": "FIXED"}.get(i['severity'], "?")
        print(f"  [{icon}] {i['field']}: {i['message']}")
    print(f"\n统计: {fixed_script.stats()}")
    
except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()


print("\n" + "=" * 60)
print("测试 2: 正常 YAML（应无修复）")
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

try:
    script2 = parse_yaml_to_script(valid_yaml, source_title="正常作品")
    fixed2, report2 = validate_and_fix_script(script2)
    val2 = report_to_dict(report2)
    
    print(f"\n通过: {val2['is_valid']}")
    print(f"问题数: {val2['total_issues']}")
    print(f"修复数: {val2['total_fixes']}")
    print(f"修复记录: {val2['fixes_applied']}")
    print(f"统计: {fixed2.stats()}")
    
except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
