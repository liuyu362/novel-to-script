"""
PR31 Step3 测试 — API 端点鉴权
验证所有 /api/works 端点：
  1. 无 token → 返回 401
  2. 无效 token → 返回 401
  3. 有效 token → 正常 CRUD
  4. 用户 A 不能操作用户 B 的作品
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# 使用独立测试数据库，避免影响运行中的后端
TEST_DB = os.path.join(os.path.dirname(__file__), "backend", "test_works.db")
os.environ["TEST_DB_PATH"] = TEST_DB

import time
import json
from fastapi.testclient import TestClient

# 临时修改 works_manager 和 user_manager 的 DB_PATH
import backend.works_manager as wm
import backend.user_manager as um

REAL_DB = wm.DB_PATH
wm.DB_PATH = TEST_DB
um.DB_PATH = TEST_DB

# 删除旧测试数据库
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

# 初始化
um.init_users_table()

from backend.app import app

client = TestClient(app)

# ── 辅助函数 ──

def register(nickname: str, password: str = "1234"):
    """注册并返回 (user_id, token)"""
    resp = client.post("/api/users/register", json={
        "nickname": nickname,
        "password": password,
    })
    assert resp.status_code == 200, f"注册失败: {resp.json()}"
    data = resp.json()["data"]
    return data["id"], data["token"]


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


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


# ═══════════════════════════════════════════════════
# 测试 1: 无 token → 401
# ═══════════════════════════════════════════════════
print("\n=== 测试 1: 无 token → 401 ===")

resp = client.get("/api/works")
check("GET /api/works 无 token → code=4006", resp.json()["code"] == 4006)

resp = client.post("/api/works", json={"original_text": "测试内容"})
check("POST /api/works 无 token → code=4006", resp.json()["code"] == 4006)

resp = client.get("/api/works/1")
check("GET /api/works/1 无 token → code=4006", resp.json()["code"] == 4006)

resp = client.put("/api/works/1", json={"title": "新标题"})
check("PUT /api/works/1 无 token → code=4006", resp.json()["code"] == 4006)

resp = client.delete("/api/works/1")
check("DELETE /api/works/1 无 token → code=4006", resp.json()["code"] == 4006)


# ═══════════════════════════════════════════════════
# 测试 2: 无效 token → 401
# ═══════════════════════════════════════════════════
print("\n=== 测试 2: 无效 token → 401 ===")

bad_headers = {"Authorization": "Bearer bad_token_123"}
resp = client.get("/api/works", headers=bad_headers)
check("GET /api/works 无效 token → code=4006", resp.json()["code"] == 4006)


# ═══════════════════════════════════════════════════
# 测试 3: 有效 token → 正常 CRUD
# ═══════════════════════════════════════════════════
print("\n=== 测试 3: 有效 token → 正常 CRUD ===")

uid_a, token_a = register("测试用户A")
h_a = auth_header(token_a)

# 创建作品
resp = client.post("/api/works", json={
    "title": "用户A的作品",
    "original_text": "这是一段测试内容"
}, headers=h_a)
check("创建作品 → code=0", resp.json()["code"] == 0)
work_id = resp.json()["data"]["id"]
check(f"创建作品 → 返回 work_id={work_id}", isinstance(work_id, int) and work_id > 0)

# 列表
resp = client.get("/api/works", headers=h_a)
check("列表 → code=0", resp.json()["code"] == 0)
check("列表 → 有1部作品", len(resp.json()["data"]) == 1)

# 读取
resp = client.get(f"/api/works/{work_id}", headers=h_a)
check("读取作品 → code=0", resp.json()["code"] == 0)
check("读取作品 → 标题正确", resp.json()["data"]["title"] == "用户A的作品")

# 更新
resp = client.put(f"/api/works/{work_id}", json={
    "title": "用户A改标题"
}, headers=h_a)
check("更新作品 → code=0", resp.json()["code"] == 0)

resp = client.get(f"/api/works/{work_id}", headers=h_a)
check("更新后 → 标题已改", resp.json()["data"]["title"] == "用户A改标题")

# 删除
resp = client.delete(f"/api/works/{work_id}", headers=h_a)
check("删除作品 → code=0", resp.json()["code"] == 0)

resp = client.get("/api/works", headers=h_a)
check("删除后 → 列表为空", len(resp.json()["data"]) == 0)


# ═══════════════════════════════════════════════════
# 测试 4: 用户 A 不能操作用户 B 的作品
# ═══════════════════════════════════════════════════
print("\n=== 测试 4: 跨用户隔离 ===")

# 用户 A 创建作品
resp = client.post("/api/works", json={
    "title": "A的私有作品",
    "original_text": "A的内容"
}, headers=h_a)
a_work_id = resp.json()["data"]["id"]

# 用户 B 注册
uid_b, token_b = register("测试用户B")
h_b = auth_header(token_b)

# B 列表为空
resp = client.get("/api/works", headers=h_b)
check("B 列表为空", len(resp.json()["data"]) == 0)

# B 不能读取 A 的作品
resp = client.get(f"/api/works/{a_work_id}", headers=h_b)
check("B 读 A 的作品 → code=4005", resp.json()["code"] == 4005)

# B 不能更新 A 的作品
resp = client.put(f"/api/works/{a_work_id}", json={"title": "B篡改"}, headers=h_b)
check("B 更新 A 的作品 → code=4005", resp.json()["code"] == 4005)

# B 不能删除 A 的作品
resp = client.delete(f"/api/works/{a_work_id}", headers=h_b)
check("B 删除 A 的作品 → code=4005", resp.json()["code"] == 4005)

# A 的作品仍然完好
resp = client.get(f"/api/works/{a_work_id}", headers=h_a)
check("A 的作品未被 B 影响", resp.json()["data"]["title"] == "A的私有作品")


# ═══════════════════════════════════════════════════
# 结果汇总
# ═══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"  结果: {passed}/{passed+failed} 通过")
print(f"{'='*50}")

# 清理
wm.DB_PATH = REAL_DB
um.DB_PATH = REAL_DB
try:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
except PermissionError:
    pass  # 文件被占用，忽略

if failed > 0:
    sys.exit(1)
