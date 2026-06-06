"""
PR32 Step4 测试 — 前端登录/注册系统
不依赖浏览器，直接测试后端 API 和前端逻辑的核心场景：
  1. 未登录 → /api/works 返回 code=4006
  2. 注册 → 返回 token
  3. 登录 → 返回 token
  4. 用 token 访问 → code=0
  5. 错误密码 → 登录失败
  6. 重复注册 → 返回错误
"""

import sys, os, time, json, threading, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))

# 启动后端（复用 pr31 的 app）
os.chdir(os.path.dirname(__file__))
os.environ["TEST_DB_PATH"] = os.path.join(os.path.dirname(__file__), "backend", "test_auth.db")

import backend.works_manager as wm
import backend.user_manager as um
import backend.app as app_module

TEST_DB = os.environ["TEST_DB_PATH"]
REAL_WM_DB = wm.DB_PATH
REAL_UM_DB = um.DB_PATH
wm.DB_PATH = TEST_DB
um.DB_PATH = TEST_DB

# 清理旧测试库
for f in [TEST_DB, TEST_DB + "-shm", TEST_DB + "-wal"]:
    if os.path.exists(f): os.remove(f)

um.init_users_table()

# 启动后端
from fastapi.testclient import TestClient
client = TestClient(app_module.app)

passed = 0
failed = 0

def check(desc, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {desc}")
    else:
        failed += 1
        print(f"  [FAIL] {desc}")

NICK = f"测试用户_{int(time.time())}"
PWD  = "test1234"

print("\n=== 测试 1: 未登录 → 401 (code=4006) ===")
resp = client.get("/api/works")
check("无 token → code=4006", resp.json()["code"] == 4006)

print("\n=== 测试 2: 注册 ===")
resp = client.post("/api/users/register", json={
    "nickname": NICK, "password": PWD
})
check("注册成功 → code=0", resp.json()["code"] == 0)
data = resp.json()["data"]
check("注册返回 token", bool(data.get("token")))
check("注册返回 nickname", data.get("nickname") == NICK)
TOKEN = data["token"]

print("\n=== 测试 3: 登录 ===")
resp = client.post("/api/users/login", json={
    "nickname": NICK, "password": PWD
})
check("登录成功 → 返回 token", bool(resp.json()["data"].get("token")))
TOKEN2 = resp.json()["data"]["token"]

print("\n=== 测试 4: 用 token 访问 API ===")
h = {"Authorization": f"Bearer {TOKEN2}"}
resp = client.get("/api/works", headers=h)
check("带 token → code=0", resp.json()["code"] == 0)

# 创建作品
resp = client.post("/api/works", 
    json={"title": "认证测试作品", "original_text": "测试内容"},
    headers=h)
check("创建作品 → code=0", resp.json()["code"] == 0)
work_id = resp.json()["data"]["id"]

resp = client.get(f"/api/works/{work_id}", headers=h)
check("读取作品 → code=0", resp.json()["code"] == 0)

print("\n=== 测试 5: 错误密码 → 登录失败 ===")
resp = client.post("/api/users/login", json={
    "nickname": NICK, "password": "wrong"
})
check("错误密码 → code!=0", resp.json()["code"] != 0)

print("\n=== 测试 6: 无效 token → 401 ===")
bad_h = {"Authorization": "Bearer bad_token_xyz"}
resp = client.get("/api/works", headers=bad_h)
check("无效 token → code=4006", resp.json()["code"] == 4006)

print("\n=== 测试 7: 重复注册 → 失败 ===")
resp = client.post("/api/users/register", json={
    "nickname": NICK, "password": PWD
})
check("重复注册 → code!=0", resp.json()["code"] != 0)

print(f"\n{'='*50}")
print(f"  结果: {passed}/{passed+failed} 通过")
print(f"{'='*50}")

# 清理
wm.DB_PATH = REAL_WM_DB
um.DB_PATH = REAL_UM_DB
for f in [TEST_DB, TEST_DB + "-shm", TEST_DB + "-wal"]:
    if os.path.exists(f):
        try: os.remove(f)
        except: pass

if failed:
    sys.exit(1)
