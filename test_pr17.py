"""
PR17 测试: 角色与场景管理页面
"""
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

PASS = 0
FAIL = 0


def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  [OK] {name}")
    except AssertionError as e:
        FAIL += 1
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        FAIL += 1
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")


print("1. 前端页面结构")
resp = requests.get(f"{BASE_URL}/", timeout=10)
html = resp.text


def _check_http():
    assert resp.status_code == 200, f"期望200，实际{resp.status_code}"
test("HTTP 200", _check_http)


def _check_page_region():
    assert 'id="page-characters"' in html, "缺少角色场景页面容器"
test("包含 page-characters 区域", _check_page_region)


def _check_mgmt():
    assert 'id="mgmtContent"' in html, "缺少管理内容区"
test("包含 mgmtContent 管理区", _check_mgmt)


def _check_charlist():
    assert 'id="charList"' in html, "缺少角色列表容器"
test("包含 charList 角色列表", _check_charlist)


def _check_scenelist():
    assert 'id="sceneListMgmt"' in html, "缺少场景列表容器"
test("包含 sceneListMgmt 场景列表", _check_scenelist)


def _check_modal():
    assert 'id="editModal"' in html, "缺少编辑模态框"
test("包含 editModal 编辑弹窗", _check_modal)


def _check_add_char():
    assert 'openAddChar()' in html, "缺少新增角色功能"
test("包含新增角色按钮", _check_add_char)


def _check_add_scene():
    assert 'openAddScene()' in html, "缺少新增场景功能"
test("包含新增场景按钮", _check_add_scene)


def _check_confirm():
    assert 'confirmMgmt()' in html, "缺少确认清单功能"
test("包含确认清单按钮", _check_confirm)


def _check_edit_char():
    assert 'openEditChar(' in html, "缺少编辑角色功能"
test("包含编辑角色按钮", _check_edit_char)


def _check_del_char():
    assert 'deleteChar(' in html, "缺少删除角色功能"
test("包含删除角色按钮", _check_del_char)


def _check_edit_scene():
    assert 'openEditScene(' in html, "缺少编辑场景功能"
test("包含编辑场景按钮", _check_edit_scene)


def _check_del_scene():
    assert 'deleteScene(' in html, "缺少删除场景功能"
test("包含删除场景按钮", _check_del_scene)


def _check_localstorage():
    assert 'localStorage.setItem' in html, "缺少 localStorage 写入"
test("localStorage 持久化", _check_localstorage)


def _check_nav_hook():
    assert 'navigateTo = function(page)' in html, "缺少页面切换挂载"
test("页面切换加载逻辑", _check_nav_hook)


print("\n2. API 端点可用性")
def _check_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.json()["code"] == 0
test("GET /api/health", _check_health)


def _check_analyze():
    r = requests.post(f"{BASE_URL}/api/analyze/novel",
        json={"text": "长安城笼罩在薄雾中，茶馆小二擦拭着柜台。一位青衫文士推门而入。"
              + "雨滴敲打窗棂的声音让巷子里格外安静。" * 2,
              "title": "测试"},
        timeout=120)
    assert r.status_code == 200
test("POST /api/analyze/novel 可访问", _check_analyze)


print(f"\n{'='*40}")
print(f"通过: {PASS} / 失败: {FAIL}")
if FAIL > 0:
    sys.exit(1)
