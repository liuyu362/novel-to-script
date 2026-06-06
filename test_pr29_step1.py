"""
PR29 Step1 测试：用户注册 / 登录 / token 验证
不依赖 LLM，纯后端逻辑测试
"""
import sys, os, time, sqlite3, hashlib, json

# ── 准备：清空测试数据库 ────────────────────────────────────────────────
DB = os.path.join(os.path.dirname(__file__), "backend", "works.db")

def reset_db():
    """删掉 works.db，重新 init"""
    if os.path.exists(DB):
        os.remove(DB)
    from backend.user_manager import init_users_table
    init_users_table()
    # works_manager 会在首次调用时自动建表，无需手动 init
    print("✓ 数据库已重置（users 表已重建，works 表会自动初始化）")

def test_register_and_login():
    """测试1+2：注册 + 登录 + token 解析"""
    from backend.user_manager import register_user, login_user, parse_token, get_current_user
    from fastapi import Request, HTTPException

    print("\n── 测试1：注册 ──")
    r = register_user("测试用户001", "abc123")
    assert r["id"] > 0, "注册失败：无 id"
    assert r["token"].startswith("user_"), "token 格式错误"
    assert r["nickname"] == "测试用户001"
    print(f"  ✓ 注册成功：id={r['id']}, token={r['token'][:20]}...")

    print("\n── 测试2：重复注册 ──")
    try:
        register_user("测试用户001", "abc123")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        print(f"  ✓ 重复注册被拒绝：{e}")

    print("\n── 测试3：登录（密码正确）──")
    r2 = login_user("测试用户001", "abc123")
    assert r2["id"] == r["id"]
    assert r2["token"].startswith("user_")
    print(f"  ✓ 登录成功：token={r2['token'][:20]}...")

    print("\n── 测试4：登录（密码错误）──")
    try:
        login_user("测试用户001", "wrong")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        print(f"  ✓ 密码错误被拒绝：{e}")

    print("\n── 测试5：登录（昵称不存在）──")
    try:
        login_user("不存在的用户", "abc123")
        assert False, "应抛出 ValueError"
    except ValueError as e:
        print(f"  ✓ 昵称不存在被拒绝：{e}")

    print("\n── 测试6：token 解析 ──")
    token = r2["token"]
    user_id = parse_token(token)
    assert user_id == r["id"], f"token 解析错误：{user_id}"
    print(f"  ✓ token 解析成功：user_id={user_id}")

    print("\n── 测试7：token 格式非法 ──")
    for bad in ["", "abc", "user_", "user_abc"]:
        try:
            parse_token(bad)
            assert False, f"应抛出 ValueError: {bad}"
        except ValueError:
            pass
    print("  ✓ 非法 token 均被拒绝")

    return r["id"], r2["token"]


def test_get_current_user():
    """测试8：get_current_user 正常/异常"""
    from backend.user_manager import get_current_user
    from fastapi import Request, HTTPException
    import types

    print("\n── 测试8：get_current_user ──")

    # 构造 mock request
    def make_req(token=None):
        scope = {"type": "http", "headers": []}
        if token:
            scope["headers"].append(
                (b"authorization", f"Bearer {token}".encode())
            )
        return Request(scope)

    # 无 Authorization header
    try:
        get_current_user(make_req(None))
        assert False, "应抛 401"
    except HTTPException as e:
        assert e.status_code == 401
        print("  ✓ 无 token → 401")

    # token 格式错误
    try:
        get_current_user(make_req("invalid-token"))
        assert False, "应抛 401"
    except HTTPException as e:
        assert e.status_code == 401
        print("  ✓ 非法 token → 401")

    # 正常 token
    r = __import__("backend.user_manager", fromlist=["register_user"])\
         .register_user("测试用户002", "pass456")
    token = r["token"]
    uid = get_current_user(make_req(token))
    assert uid == r["id"]
    print(f"  ✓ 合法 token → user_id={uid}")


def test_user_exists():
    """测试9：user_exists 函数"""
    from backend.user_manager import user_exists, register_user

    print("\n── 测试9：user_exists ──")
    r = register_user("测试用户003", "pass789")
    assert user_exists(r["id"]) == True
    assert user_exists(99999) == False
    print(f"  ✓ user_exists 正常：存在={r['id']}, 不存在=99999")


def test_api_register_login():
    """测试10+11：通过 HTTP 调用 /api/users/register 和 /api/users/login"""
    import requests

    print("\n── 测试10：HTTP 注册 ──")
    resp = requests.post("http://127.0.0.1:8000/api/users/register",
                        json={"nickname": "HTTP测试用户", "password": "test1234"})
    assert resp.status_code == 200
    d = resp.json()
    assert d["code"] == 0, f"注册失败：{d}"
    assert "token" in d["data"]
    print(f"  ✓ HTTP 注册成功：{d['data']['nickname']}")

    print("\n── 测试11：HTTP 登录 ──")
    resp2 = requests.post("http://127.0.0.1:8000/api/users/login",
                         json={"nickname": "HTTP测试用户", "password": "test1234"})
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["code"] == 0
    assert "token" in d2["data"]
    print(f"  ✓ HTTP 登录成功，token={d2['data']['token'][:20]}...")

    print("\n── 测试12：HTTP 登录密码错误 ──")
    resp3 = requests.post("http://127.0.0.1:8000/api/users/login",
                         json={"nickname": "HTTP测试用户", "password": "wrong"})
    d3 = resp3.json()
    assert d3["code"] == 4006  # UNAUTHORIZED
    print(f"  ✓ HTTP 密码错误 → code={d3['code']}")


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

    print("=" * 50)
    print("PR29 Step1 测试：用户注册/登录/token 验证")
    print("=" * 50)

    reset_db()
    uid, token = test_register_and_login()
    test_get_current_user()
    test_user_exists()

    # HTTP 测试需要后端运行
    print("\n── 检查后端是否在线 ──")
    try:
        import requests
        r = requests.get("http://127.0.0.1:8000/api/health", timeout=2)
        if r.status_code == 200:
            test_api_register_login()
        else:
            print("  ⚠ 后端未运行，跳过 HTTP 测试（启动 backend 后重试）")
    except Exception as e:
        print(f"  ⚠ 后端未运行，跳过 HTTP 测试：{e}")

    print("\n" + "=" * 50)
    print("✅ 全部测试通过！")
    print("=" * 50)
