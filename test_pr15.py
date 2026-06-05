"""PR15 测试：前端架子 + StaticFiles 挂载"""

import requests
import sys

BASE = "http://localhost:8000"
passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  [OK] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}")
        failed += 1


# ── 测试 1: API 健康检查正常 ──
print("1. API 健康检查正常")
try:
    r = requests.get(f"{BASE}/api/health", timeout=5)
    check("状态码 200", r.status_code == 200)
    data = r.json()
    check("code == 0", data.get("code") == 0)
except Exception as e:
    check(f"请求成功 ({e})", False)


# ── 测试 2: 根路径返回前端页面 ──
print("\n2. 根路径返回前端页面")
try:
    r = requests.get(f"{BASE}/", timeout=5)
    check("状态码 200", r.status_code == 200)
    check("包含 HTML 标签", "<html" in r.text)
    check("包含标题", "AI 小说转剧本工具" in r.text)
    check("包含步骤导航", "上传解读" in r.text)
    check("包含 5 个步骤", r.text.count("step-num") >= 5)
except Exception as e:
    check(f"请求成功 ({e})", False)


# ── 测试 3: 非 /api 路径也返回前端 (SPA 路由) ──
print("\n3. SPA 路由转发")
try:
    r = requests.get(f"{BASE}/any-page", timeout=5)
    check("状态码 200", r.status_code == 200)
    check("返回 index.html", "AI 小说转剧本工具" in r.text)
except Exception as e:
    check(f"请求成功 ({e})", False)


# ── 测试 4: /api 路径不受影响 ──
print("\n4. /api 路径不受影响")
try:
    r = requests.get(f"{BASE}/api/versions", timeout=5)
    check("状态码 200", r.status_code == 200)
    data = r.json()
    check("返回 JSON", isinstance(data, dict))
    check("code == 0", data.get("code") == 0)
except Exception as e:
    check(f"请求成功 ({e})", False)


# ── 测试 5: 静态文件可访问 ──
print("\n5. 静态文件访问")
# 通过 /static/ 前缀访问
try:
    r = requests.get(f"{BASE}/static/index.html", timeout=5)
    check("状态码 200", r.status_code == 200)
    check("包含标题", "AI 小说转剧本工具" in r.text)
except Exception as e:
    check(f"请求成功 ({e})", False)


# ── 汇总 ──
print(f"\n{'='*40}")
print(f"通过: {passed} / 失败: {failed}")
if failed > 0:
    print("存在失败项")
    sys.exit(1)
else:
    print("全部通过")
