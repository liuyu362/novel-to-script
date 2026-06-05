"""
PR19 测试：逻辑矛盾检测
前端 DOM 结构 + API 端点 + 数据流
"""
import json
import requests
import traceback

BASE = "http://127.0.0.1:8000"
PASSED = 0
FAILED = 0
ERRORS = []

SAMPLE_YAML = """meta:
  title: 江湖夜雨
  version: 电影版
scenes:
- scene_id: Scene_1
  location: 青云茶馆
  time: 清晨
  characters_present:
  - 李青云
  - 小二
  events:
  - 李青云收到密信
- scene_id: Scene_2
  location: 城外竹林
  time: 正午
  characters_present:
  - 李青云
  - 黑衣刺客
  events:
  - 遭遇伏击，李青云受伤逃脱"""

SAMPLE_TEXT = "李青云推开茶馆的门，细雨飘进屋内。小二迎上前去，递上一封密信。李青云在靠窗位置坐下，展开信笺，面色凝重。他匆匆离开茶馆，策马赶往城外竹林。正午时分，竹林深处，数名黑衣刺客从天而降，李青云拔剑迎战，左臂中了一剑，但仍杀出重围。"


def check(desc, condition):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {desc}")
    else:
        FAILED += 1
        msg = f"  FAIL  {desc}"
        print(msg)
        ERRORS.append(msg)


def test_frontend_dom():
    """前端 HTML 结构验证"""
    print("\n--- 前端 DOM 结构 ---")
    resp = requests.get(BASE + "/")
    html = resp.text

    # 页面结构
    check("步骤4「逻辑检测」存在", '<div class="step" data-page="detect">' in html)
    check("page-detect 容器存在", 'id="page-detect"' in html)
    check("空状态提示 detectEmpty", 'id="detectEmpty"' in html)
    check("内容区 detectContent", 'id="detectContent"' in html)
    check("检测按钮 btnDetect", 'id="btnDetect"' in html)
    check("结果面板 detectResultPanel", 'id="detectResultPanel"' in html)
    check("统计概览 detectSummary", 'id="detectSummary"' in html)
    check("筛选标签 filterTabs", 'id="filterTabs"' in html)
    check("问题列表 issueList", 'id="issueList"' in html)
    check("无问题提示 detectNoIssues", 'id="detectNoIssues"' in html)

    # 筛选标签项
    check("筛选: 全部", 'data-filter="all"' in html)
    check("筛选: 角色一致性", 'data-filter="character_consistency"' in html)
    check("筛选: 场景连续性", 'data-filter="scene_continuity"' in html)
    check("筛选: 时间线", 'data-filter="timeline"' in html)
    check("筛选: 情节漏洞", 'data-filter="plot_hole"' in html)

    # JS 函数
    check("startDetect 函数", 'function startDetect()' in html)
    check("renderDetectResult 函数", 'function renderDetectResult(data)' in html)
    check("filterIssues 函数", 'function filterIssues(filter)' in html)
    check("loadDetectData 函数", 'function loadDetectData()' in html)
    check("navigateTo hooks detect", "page === 'detect'" in html)

    # CSS 类
    check("issue-card 样式", '.issue-card {' in html)
    check("severity-badge 样式", '.severity-badge {' in html)
    check("type-label 样式", '.type-label {' in html)
    check("detect-summary 样式", '.detect-summary {' in html)
    check("filter-tabs 样式", '.filter-tabs {' in html)


def test_api_endpoint():
    """API 端点测试"""
    print("\n--- API 端点 ---")

    # 1. 正常检测
    print("  [正常检测 - 调用 LLM，可能需要1-2分钟]")
    resp = requests.post(BASE + "/api/check/logic", json={
        "script_yaml": SAMPLE_YAML,
        "original_text": SAMPLE_TEXT,
        "title": "江湖夜雨",
    })
    data = resp.json()
    check("正常检测返回 code=0", data.get("code") == 0)
    check("正常检测含 issues", "issues" in data.get("data", {}))
    check("正常检测含 summary", "summary" in data.get("data", {}))
    summary = data.get("data", {}).get("summary", {})
    check("summary 含 total", "total" in summary)
    check("summary 含 critical", "critical" in summary)
    check("summary 含 warning", "warning" in summary)
    check("summary 含 info", "info" in summary)

    issues = data.get("data", {}).get("issues", [])
    if issues:
        iss0 = issues[0]
        check("issue 有 type", "type" in iss0)
        check("issue 有 severity", "severity" in iss0)
        check("issue 有 description", "description" in iss0)
        check("issue 有 suggestion", "suggestion" in iss0)
        check("severity 合法", iss0.get("severity") in ("critical", "warning", "info"))

    # 2. 缺少 script_yaml
    resp = requests.post(BASE + "/api/check/logic", json={
        "original_text": SAMPLE_TEXT,
        "title": "test",
    })
    data = resp.json()
    check("缺少 script_yaml 返回非0", data.get("code") != 0)

    # 3. 缺少 original_text
    resp = requests.post(BASE + "/api/check/logic", json={
        "script_yaml": SAMPLE_YAML,
        "title": "test",
    })
    data = resp.json()
    check("缺少 original_text 返回非0", data.get("code") != 0)

    # 4. script_yaml 过短
    resp = requests.post(BASE + "/api/check/logic", json={
        "script_yaml": "太短",
        "original_text": SAMPLE_TEXT,
        "title": "test",
    })
    data = resp.json()
    check("script_yaml 过短返回非0", data.get("code") != 0)

    # 5. original_text 过短
    resp = requests.post(BASE + "/api/check/logic", json={
        "script_yaml": SAMPLE_YAML,
        "original_text": "一二三四五",
        "title": "test",
    })
    data = resp.json()
    check("original_text 过短返回非0", data.get("code") != 0)

    # 6. 空文本检测
    resp = requests.post(BASE + "/api/check/logic", json={
        "script_yaml": "",
        "original_text": "",
        "title": "test",
    })
    data = resp.json()
    check("空文本返回非0", data.get("code") != 0)

    # 验证正常检测结果的 issue 结构
    print("  [正常检测结果验证]")
    if issues:
        valid_types = {"character_consistency", "scene_continuity", "timeline", "plot_hole", "unknown"}
        for i, iss in enumerate(issues):
            check(f"issue[{i}] type 合法", iss.get("type") in valid_types)
    else:
        check("无问题 - issues 为空数组合法", issues == [])


if __name__ == "__main__":
    print("=" * 50)
    print("PR19 逻辑检测测试")
    print("=" * 50)

    try:
        requests.get(BASE + "/api/health", timeout=5)
    except Exception:
        print("ERROR: 服务器未运行 (python backend/server.py)")
        exit(1)

    test_frontend_dom()
    test_api_endpoint()

    total = PASSED + FAILED
    print("\n" + "=" * 50)
    print(f"结果: {PASSED}/{total} 通过")
    if ERRORS:
        print("失败项:")
        for e in ERRORS:
            print(f"  {e}")
    print("=" * 50)
