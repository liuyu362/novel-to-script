"""
PR18 测试: 剧本改编页面

覆盖:
- 前端 DOM 结构 (版本选择器、改编按钮、输出面板)
- API 端点 GET /api/health, GET /api/versions, POST /api/convert/fusion
- localStorage 持久化 (novelAnalysis/novelRawText/novelTitle/novelScript)
"""

import re
import json
import requests

SERVER = "http://127.0.0.1:8000"
FRONTEND = "F:/七牛云议题/novel-to-script/frontend/index.html"

TEST_TEXT = (
    "夜幕低垂，长安城笼罩在暮色之中。一条青石板路通向城门。"
    "李青云骑着一匹黑马缓缓前行，他目光如炬，不时扫视周围。"
    "忽然前方传来刀兵相击之声，李青云勒住缰绳。"
)

FAIL = 0
PASS = 0


def record(test_id, label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [{test_id}] PASS: {label}")
    else:
        FAIL += 1
        print(f"  [{test_id}] FAIL: {label}" + (f" ({detail})" if detail else ""))


def check_api(test_id, label, url, method="get", payload=None, checks=None):
    """通用 API 测试"""
    try:
        if method == "get":
            r = requests.get(url, timeout=15)
        else:
            r = requests.post(url, json=payload, timeout=120)
        record(test_id, label, r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200 and checks:
            data = r.json() if r.text else {}
            for check_name, check_fn in checks.items():
                record(test_id, f"{label} → {check_name}", check_fn(data), str(data.get('message', '')))
        return r
    except Exception as e:
        record(test_id, label, False, f"exception: {str(e)[:80]}")
        return None


print("=== PR18 测试: 剧本改编页面 ===\n")

# ── 1. 前端 HTML 结构测试 ──
print("--- 前端 DOM ---")
with open(FRONTEND, "r", encoding="utf-8") as f:
    html = f.read()

# 版本选择器
def check_dom(test_id, label, pattern):
    cond = re.search(pattern, html) is not None
    record(test_id, label, cond)

check_dom("D01", "页面 #page-adapt 存在", r'id="page-adapt"')
check_dom("D02", "adaptEmpty 空状态", r'id="adaptEmpty"')
check_dom("D03", "adaptContent 内容区", r'id="adaptContent"')
check_dom("D04", "电影版选项", r'data-version="movie"')
check_dom("D05", "电视剧版选项", r'data-version="tv_series"')
check_dom("D06", "舞台剧版选项", r'data-version="stage_play"')
check_dom("D07", "版本选择器容器", r'id="versionSelector"')
check_dom("D08", "改编按钮 btnAdapt", r'id="btnAdapt"')
check_dom("D09", "剧本输出面板", r'id="scriptOutputCard"')
check_dom("D10", "剧本输出代码区", r'id="scriptOutput"')
check_dom("D11", "复制按钮", r'id="btnCopy"')
check_dom("D12", "下载按钮 btn-download", r'class="btn-sm btn-download"')
check_dom("D13", "重新生成按钮 btn-retry", r'class="btn-sm btn-retry"')
check_dom("D14", "selectVersion 函数", r'function selectVersion')
check_dom("D15", "loadAdaptData 函数", r'function loadAdaptData')
check_dom("D16", "startAdapt 函数", r'function startAdapt')
check_dom("D17", "renderScript 函数", r'function renderScript')
check_dom("D18", "copyScript 函数", r'function copyScript')
check_dom("D19", "downloadScript 函数", r'function downloadScript')
check_dom("D20", "navigateTo 钩子含 adapt", r"page === 'adapt'")
check_dom("D21", "CSS version-selector", r'\.version-selector')
check_dom("D22", "CSS version-opt", r'\.version-opt')
check_dom("D23", "CSS script-output (暗色)", r'\.script-output \{')
check_dom("D24", "CSS btn-copy", r'\.btn-copy')
check_dom("D25", "CSS YAML 高亮 yaml-key", r'\.yaml-key')
check_dom("D26", "上传页存 novelRawText", r"setItem\('novelRawText'")
check_dom("D27", "上传页存 novelTitle", r"setItem\('novelTitle'")

print(f"\nDOM: {PASS} pass / {FAIL + PASS} total\n")

# ── 2. API 端点测试 ──
print("--- API 端点 ---")
api_pass = PASS
api_fail = FAIL

# Health
check_api("A01", "GET /api/health",
          f"{SERVER}/api/health",
          checks={"code==0": lambda d: d.get("code") == 0})

# Versions
check_api("A02", "GET /api/versions",
          f"{SERVER}/api/versions",
          checks={"3 versions": lambda d: len(d.get("data", [])) == 3})

# Fusion convert
r = check_api("A03", "POST /api/convert/fusion (movie)",
              f"{SERVER}/api/convert/fusion", method="post",
              payload={"text": TEST_TEXT, "title": "测试", "version": "movie"},
              checks={
                  "code==0": lambda d: d.get("code") == 0,
                  "has script": lambda d: "script" in d.get("data", {}),
                  "has analysis": lambda d: "analysis" in d.get("data", {}),
                  "has characters": lambda d: "characters" in d.get("data", {}).get("analysis", {}),
              })

# TV series version
check_api("A04", "POST /api/convert/fusion (tv_series)",
          f"{SERVER}/api/convert/fusion", method="post",
          payload={"text": TEST_TEXT, "title": "测试", "version": "tv_series"},
          checks={"code==0": lambda d: d.get("code") == 0})

# Stage play version
check_api("A05", "POST /api/convert/fusion (stage_play)",
          f"{SERVER}/api/convert/fusion", method="post",
          payload={"text": TEST_TEXT, "title": "测试", "version": "stage_play"},
          checks={"code==0": lambda d: d.get("code") == 0})

# Short text validation
check_api("A06", "POST /api/convert/fusion (text < 50 字)",
          f"{SERVER}/api/convert/fusion", method="post",
          payload={"text": "太短", "title": "测试"},
          checks={"code!=0": lambda d: d.get("code") != 0})

# Empty text validation
check_api("A07", "POST /api/convert/fusion (empty text)",
          f"{SERVER}/api/convert/fusion", method="post",
          payload={"text": "", "title": "测试"},
          checks={"code!=0": lambda d: d.get("code") != 0})

api_passed = PASS - api_pass
api_total = (PASS - api_pass) + (FAIL - api_fail)
print(f"\nAPI: {api_passed} pass / {api_total} total\n")

# ── 3. 结果 ──
total_pass = PASS
total_fail = FAIL
print(f"{'='*40}")
print(f"RESULT: {total_pass}/{total_pass + total_fail} 通过")
if total_fail > 0:
    print(f"FAILED TESTS: {total_fail}")
    exit(1)
else:
    print("ALL TESTS PASSED")
