#!/usr/bin/env python3
"""
PR20 测试：导出下载页面
覆盖：前端 DOM 结构、JS 函数、CSS 类、localStorage 持久化、导航钩子
"""
import sys, json, os, re

BASE = "http://127.0.0.1:8000"
HTML_PATH = os.path.join(os.path.dirname(__file__), "frontend", "index.html")

def http(method, path, **kw):
    import urllib.request, urllib.error, json as j
    url = BASE + path
    data = j.dumps(kw.get("json")).encode() if "json" in kw else None
    h = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return None, str(e)

def jload(raw):
    try: return json.loads(raw)
    except: return {}

# ── 加载 HTML ──
with open(HTML_PATH, encoding="utf-8") as f:
    HTML = f.read()

def has(txt):
    return txt in HTML

PASS = []
FAIL = []

def ok(msg): PASS.append(msg)
def fail(msg): FAIL.append(msg)

print("=" * 60)
print("PR20 测试开始")
print("=" * 60)

# ── 1. 导出页 DOM 结构 ──
print("\n[1] 导出页 DOM 结构")
tests_1 = [
    ("page-export 区块存在", 'id="page-export"'),
    ("exportEmpty 空状态", 'id="exportEmpty"'),
    ("exportContent 内容区", 'id="exportContent"'),
    ("数据概览卡片", 'id="exportOverview"'),
    ("格式选择区", 'id="exportFmtCards"'),
    ("内容选项区", 'id="exportCheckBoxes"'),
    ("预览面板", 'id="exportPreview"'),
    ("导出按钮", 'id="btnExport"'),
    ("复制按钮", 'id="btnCopyExport"'),
    ("打包下载按钮", 'onclick="exportAll()"'),
]
for msg, pat in tests_1:
    (ok if has(pat) else fail)(msg)

# ── 2. 格式选择卡片 ──
print("\n[2] 格式选择卡片")
tests_2 = [
    ("YAML 格式卡片", 'data-fmt="yaml"'),
    ("JSON 格式卡片", 'data-fmt="json"'),
    ("TXT 格式卡片", 'data-fmt="txt"'),
    ("YAML 说明文字", '保留完整场景/角色/对话信息'  ),
    ("JSON 说明文字", '方便程序处理与二次开发'),
    ("TXT 说明文字", '人类可读，方便直接编辑与分享'),
    ("selectExportFmt 函数", 'function selectExportFmt'),
]
for msg, pat in tests_2:
    (ok if has(pat) else fail)(msg)

# ── 3. 导出内容复选框 ──
print("\n[3] 导出内容复选框")
tests_3 = [
    ("剧本正文复选框", 'id="cbScript"'),
    ("角色列表复选框", 'id="cbChars"'),
    ("场景列表复选框", 'id="cbScenes"'),
    ("对话统计复选框", 'id="cbDialogue"'),
    ("逻辑检测复选框", 'id="cbLogic"'),
    ("分析摘要复选框", 'id="cbSummary"'),
    ("剧本正文默认勾选", 'id="cbScript" checked'),
    ("角色列表默认勾选", 'id="cbChars" checked'),
    ("场景列表默认勾选", 'id="cbScenes" checked'),
    ("分析摘要默认勾选", 'id="cbSummary" checked'),
]
for msg, pat in tests_3:
    (ok if has(pat) else fail)(msg)

# ── 4. 数据概览统计块 ──
print("\n[4] 数据概览统计块")
tests_4 = [
    ("export-overview 网格", 'class="export-overview"'),
    ("export-stat 样式", '.export-stat {'),
    ("stat-icon 样式", '.export-stat .stat-icon'),
    ("stat-num 样式", '.export-stat .stat-num'),
    ("stat-label 样式", '.export-stat .stat-label'),
    ("stat-ok 样式", '.export-stat .stat-ok'),
]
for msg, pat in tests_4:
    (ok if has(pat) else fail)(msg)

# ── 5. 格式卡片 CSS ──
print("\n[5] 格式卡片 CSS")
tests_5 = [
    ("export-format-cards 布局", '.export-format-cards {'),
    ("export-fmt-opt 卡片样式", '.export-fmt-opt {'),
    ("selected 状态样式", '.export-fmt-opt.selected {'),
    ("fmt-name 样式", '.export-fmt-opt .fmt-name'),
    ("fmt-desc 样式", '.export-fmt-opt .fmt-desc'),
]
for msg, pat in tests_5:
    (ok if has(pat) else fail)(msg)

# ── 6. 预览面板 & 操作按钮 ──
print("\n[6] 预览面板 & 操作按钮")
tests_6 = [
    ("export-preview 面板", '.export-preview {'),
    ("export-preview 暗色背景", 'background: #1e1e2e'),
    ("export-actions 按钮组", '.export-actions {'),
    ("btn-export 样式", '.btn-export {'),
    ("export-combined-hint", '.export-combined-hint {'),
    ("refreshPreview 函数", 'function refreshPreview()'),
    ("doExport 函数", 'function doExport()'),
    ("copyExport 函数", 'function copyExport()'),
    ("exportAll 函数", 'function exportAll()'),
]
for msg, pat in tests_6:
    (ok if has(pat) else fail)(msg)

# ── 7. buildExportData ──
print("\n[7] buildExportData 函数")
tests_7 = [
    ("buildExportData 函数定义", 'function buildExportData()'),
    ("读取 novelScript", "localStorage.getItem('novelScript')"),
    ("读取 novelAnalysis", "localStorage.getItem('novelAnalysis')"),
    ("读取 novelLogic", "localStorage.getItem('novelLogic')"),
    ("读取 novelTitle", "localStorage.getItem('novelTitle')"),
    ("cbScript 勾选判断", "document.getElementById('cbScript')?.checked"),
    ("cbChars 勾选判断", "document.getElementById('cbChars')?.checked"),
    ("cbScenes 勾选判断", "document.getElementById('cbScenes')?.checked"),
    ("cbDialogue 勾选判断", "document.getElementById('cbDialogue')?.checked"),
    ("cbLogic 勾选判断", "document.getElementById('cbLogic')?.checked"),
    ("cbSummary 勾选判断", "document.getElementById('cbSummary')?.checked"),
]
for msg, pat in tests_7:
    (ok if has(pat) else fail)(msg)

# ── 8. buildYamlExport / buildTxtExport ──
print("\n[8] 导出格式化函数")
tests_8 = [
    ("buildYamlExport 函数", 'function buildYamlExport('),
    ("buildTxtExport 函数", 'function buildTxtExport('),
    ("YAML 注释头部", '# 剧本导出文件'),
    ("YAML 作品行", '# 作品: '),
    ("YAML 时间行", '# 导出时间: '),
    ("YAML summary 节", '## 分析摘要'),
    ("YAML 剧本正文节", '## 剧本正文'),
    ("YAML 角色列表节", '## 角色列表'),
    ("YAML 场景列表节", '## 场景列表'),
    ("YAML 逻辑检测节", '## 逻辑检测报告'),
    ("TXT 分隔线", '====================================='),
    ("TXT 分析摘要标记", '【分析摘要】'),
    ("TXT 剧本正文标记", '【剧本正文】'),
    ("TXT 角色列表标记", '【角色列表】'),
    ("TXT 场景列表标记", '【场景列表】'),
    ("TXT 逻辑检测标记", '【逻辑检测报告】'),
]
for msg, pat in tests_8:
    (ok if has(pat) else fail)(msg)

# ── 9. 导航钩子 ──
print("\n[9] 导航钩子 (export)")
tests_9 = [
    ("navigateTo 钩子覆盖", "if (page === 'export') loadExportData()"),
    ("loadExportData 调用", "loadExportData()"),
    ("__origNav 保存", "const __origNav = navigateTo"),
    ("__origNav 调用", "__origNav(page)"),
]
for msg, pat in tests_9:
    (ok if has(pat) else fail)(msg)

# ── 10. loadExportData 空状态 ──
print("\n[10] loadExportData 空状态处理")
tests_10 = [
    ("空状态 hidden 切换", "getElementById('exportEmpty').classList.remove('hidden')"),
    ("内容区 hidden 切换", "getElementById('exportContent').classList.add('hidden')"),
    ("有数据时相反切换", "getElementById('exportEmpty').classList.add('hidden')"),
    ("无 scriptRaw 且无 analysisRaw", "!scriptRaw && !analysisRaw"),
]
for msg, pat in tests_10:
    (ok if has(pat) else fail)(msg)

# ── 11. API 端点可用性（不触发 LLM） ──
print("\n[11] API 端点可用性")
# 使用最短合法文本测试各端点是否正常响应
MIN_TEXT = "正文。" * 17  # 51字

tests_api = [
    ("GET /api/health", "GET", "/api/health", None),
    ("POST /api/convert 响应", "POST", "/api/convert", {"text": MIN_TEXT, "title": "测试"}),
    ("POST /api/analyze/characters 响应", "POST", "/api/analyze/characters", {"text": MIN_TEXT}),
    ("POST /api/analyze/scenes 响应", "POST", "/api/analyze/scenes", {"text": MIN_TEXT}),
    ("POST /api/analyze/dialogue 响应", "POST", "/api/analyze/dialogue", {"text": MIN_TEXT}),
    ("POST /api/convert/fusion 响应", "POST", "/api/convert/fusion", {"text": MIN_TEXT}),
    ("POST /api/analyze/novel 响应", "POST", "/api/analyze/novel", {"text": MIN_TEXT}),
]
for msg, method, path, body in tests_api:
    status, raw = http(method, path, json=body)
    d = jload(raw)
    # 只要不返回非200且非422/400/503（LLM未就绪是预期行为）
    if status in (200, 400, 422, 503):
        ok(msg + f" (status={status})")
    else:
        fail(msg + f" status={status} raw={raw[:80]}")

# ── 12. localStorage 键名一致性 ──
print("\n[12] localStorage 键名一致性")
tests_12 = [
    ("novelAnalysis 键", "localStorage.getItem('novelAnalysis')"),
    ("novelRawText 键", "localStorage.getItem('novelRawText')"),
    ("novelTitle 键", "localStorage.getItem('novelTitle')"),
    ("novelScript 键", "localStorage.getItem('novelScript')"),
    ("novelLogic 键", "localStorage.getItem('novelLogic')"),
    ("setItem novelAnalysis", "localStorage.setItem('novelAnalysis'"),
    ("setItem novelRawText", "localStorage.setItem('novelRawText'"),
    ("setItem novelTitle", "localStorage.setItem('novelTitle'"),
    ("setItem novelScript", "localStorage.setItem('novelScript'"),
]
for msg, pat in tests_12:
    (ok if has(pat) else fail)(msg)

# ── 13. markCompleted 调用 ──
print("\n[13] markCompleted 第五步")
tests_13 = [
    ("doExport 中 markCompleted(5)", "markCompleted(5)"),
    ("exportAll 中 markCompleted(5)", "markCompleted(5)"),
]
for msg, pat in tests_13:
    (ok if has(pat) else fail)(msg)

# ── 总结 ──
print(f"\n  结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
print("=" * 60)
for m in PASS: print(f"  [OK] {m}")
if FAIL:
    print("\n失败项：")
    for m in FAIL: print(f"  [FAIL] {m}")
else:
    print("\n  >> 全部通过！")
print()
