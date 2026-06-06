"""
PR30 Step2 测试：works 表 user_id 隔离
"""
import sys, os, sqlite3, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

DB = os.path.join(os.path.dirname(__file__), "backend", "works.db")

# 绕过文件锁：临时修改 works_manager 的 DB_PATH 指向测试用数据库
import backend.works_manager as wm
TEST_DB = os.path.join(os.path.dirname(__file__), "backend", "test_works.db")
wm.DB_PATH = TEST_DB

# 同理修改 user_manager 的 DB_PATH
import backend.user_manager as um
um.DB_PATH = TEST_DB

def reset_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    from backend.user_manager import init_users_table
    init_users_table()
    # 手动初始化 works 表（因为 _get_conn 只在 need_init 时建表）
    from backend.works_manager import _get_conn
    _get_conn()  # 触发建表
    print("✓ 测试数据库已重置")

def test_multi_user_isolation():
    """测试多用户作品隔离"""
    from backend.user_manager import register_user
    from backend.works_manager import create_work, list_works, get_work, update_work, delete_work

    print("\n── 创建两个用户 ──")
    ua = register_user("用户A", "aaa111")
    ub = register_user("用户B", "bbb222")
    print(f"  用户A: id={ua['id']}")
    print(f"  用户B: id={ub['id']}")

    print("\n── 用户A创建两个作品 ──")
    w1 = create_work("A的作品1", "用户A的小说内容1", ua["id"])
    w2 = create_work("A的作品2", "用户A的小说内容2", ua["id"])
    print(f"  A的作品1: id={w1}, A的作品2: id={w2}")

    print("\n── 用户B创建一个作品 ──")
    w3 = create_work("B的作品1", "用户B的小说内容", ub["id"])
    print(f"  B的作品1: id={w3}")

    print("\n── 测试1：用户A看到2个作品 ──")
    a_works = list_works(ua["id"])
    assert len(a_works) == 2, f"用户A应看到2个作品，实际{len(a_works)}"
    a_ids = {w["id"] for w in a_works}
    assert w1 in a_ids and w2 in a_ids, "用户A的作品ID不正确"
    print(f"  ✓ 用户A看到 {len(a_works)} 个作品：{[w['title'] for w in a_works]}")

    print("\n── 测试2：用户B只看到1个作品 ──")
    b_works = list_works(ub["id"])
    assert len(b_works) == 1, f"用户B应看到1个作品，实际{len(b_works)}"
    assert b_works[0]["id"] == w3
    print(f"  ✓ 用户B看到 1 个作品：{b_works[0]['title']}")

    print("\n── 测试3：用户B拿不到用户A的作品 ──")
    assert get_work(w1, ub["id"]) is None, "用户B不应能读取用户A的作品"
    print("  ✓ 用户B无法读取A的作品")

    print("\n── 测试4：用户A读取自己的作品正常 ──")
    a1 = get_work(w1, ua["id"])
    assert a1 is not None
    assert a1["title"] == "A的作品1"
    assert a1["original_text"] == "用户A的小说内容1"
    print(f"  ✓ 读取成功：{a1['title']}")

    print("\n── 测试5：用户B不能更新用户A的作品 ──")
    ok = update_work(w1, ub["id"], title="被B改坏了")
    assert ok == False, "用户B不应能更新A的作品"
    # 验证没被改动
    a1_after = get_work(w1, ua["id"])
    assert a1_after["title"] == "A的作品1", "标题不应被改动"
    print("  ✓ B无法更新A的作品，标题未变")

    print("\n── 测试6：用户A更新自己的作品正常 ──")
    ok = update_work(w1, ua["id"], title="A的新标题", current_step=2)
    assert ok == True
    a1_updated = get_work(w1, ua["id"])
    assert a1_updated["title"] == "A的新标题"
    assert a1_updated["current_step"] == 2
    print(f"  ✓ 更新成功：{a1_updated['title']}, step={a1_updated['current_step']}")

    print("\n── 测试7：用户B不能删除用户A的作品 ──")
    ok = delete_work(w1, ub["id"])
    assert ok == False
    assert get_work(w1, ua["id"]) is not None, "作品不应被删除"
    print("  ✓ B无法删除A的作品")

    print("\n── 测试8：用户A删除自己的作品 ──")
    ok = delete_work(w2, ua["id"])
    assert ok == True
    assert get_work(w2, ua["id"]) is None, "作品应已被删除"
    a_works_after = list_works(ua["id"])
    assert len(a_works_after) == 1, f"删除后应剩1个作品"
    print(f"  ✓ 删除成功，A剩余 {len(a_works_after)} 个作品")


def test_empty_user():
    """测试新用户没有作品"""
    from backend.user_manager import register_user
    from backend.works_manager import list_works

    print("\n── 测试9：新用户作品列表为空 ──")
    u = register_user("新用户", "pass123")
    works = list_works(u["id"])
    assert works == [], f"新用户应为空列表，实际{works}"
    print("  ✓ 新用户作品列表为空")


if __name__ == "__main__":
    print("=" * 50)
    print("PR30 Step2 测试：works 表 user_id 隔离")
    print("=" * 50)

    reset_db()
    test_multi_user_isolation()
    test_empty_user()

    print("\n" + "=" * 50)
    print("✅ 全部测试通过！")
    print("=" * 50)
