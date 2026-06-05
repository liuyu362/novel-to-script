"""
PR11 测试脚本：角色列表自动提取
"""
import urllib.request
import urllib.error
import json
import time


API = "http://127.0.0.1:8000"

TEST_TEXT = """林默走在深夜的街道上，风把他的外套吹得猎猎作响。
他想起三天前和父亲的那场争吵——"你根本不懂我在做什么！"父亲的声音还在耳边回荡。

"林默哥！"身后传来一个清脆的声音。是苏晓，他的大学同学，也是唯一愿意听他倾诉的人。

苏晓跑过来，喘着气说："我听说你辞职了？伯父知道了肯定很生气吧。"

林默苦笑了一下。就在这时，一个黑影从巷口闪过。
"谁？"林默警觉地回头。

黑影没有回答，只是静静伫立在路灯下。借着昏黄的光线，林默看清了那张脸——竟然是已经失踪两年的哥哥，林皓。

"哥？！"林默冲了过去，但林皓转身就跑，消失在夜色中。
"""


pass_count = 0
fail_count = 0


def test(name, fn):
    global pass_count, fail_count
    print(f"\n{'=' * 50}")
    print(f"测试：{name}")
    print(f"{'=' * 50}")
    try:
        result = fn()
        if result:
            pass_count += 1
            print(f"  ✅ PASSED")
        else:
            fail_count += 1
            print(f"  ❌ FAILED")
    except Exception as e:
        fail_count += 1
        print(f"  ❌ FAILED: {e}")


def check_server():
    try:
        r = urllib.request.urlopen(f"{API}/api/health", timeout=5)
        d = json.loads(r.read())
        print(f"  服务状态: {d['data']['status']}")
        print(f"  LLM就绪: {d['data']['llm_ready']}")
        return d["data"]["llm_ready"]
    except Exception as e:
        print(f"  ❌ 无法连接服务: {e}")
        return False


def test_analyze_characters():
    """正常请求：带标题"""
    payload = json.dumps({
        "text": TEST_TEXT,
        "title": "夜色中的重逢"
    }).encode()

    req = urllib.request.Request(
        f"{API}/api/analyze/characters",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    start = time.time()
    r = urllib.request.urlopen(req, timeout=120)
    elapsed = time.time() - start

    d = json.loads(r.read())
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  code: {d['code']}")
    print(f"  message: {d['message']}")

    assert d["code"] == 0, f"code != 0: {d}"
    data = d["data"]
    print(f"  文本长度: {data['text_length']}")
    print(f"  角色总数: {data['total']}")

    chars = data["characters"]
    print(f"  角色列表:")
    for c in chars:
        print(f"    - {c['name']} ({c['gender']}, {c['role_type']}): {c['description']}")

    dist = data["role_distribution"]
    print(f"  角色分布: {dist}")

    assert data["total"] >= 2, f"角色数太少: {data['total']}"
    assert len(chars) == data["total"]
    return True


def test_analyze_no_title():
    """无标题：title 字段可选，应正常处理"""
    payload = json.dumps({
        "text": "张三和李四一起走进了咖啡店。张三说：'今天天气真好。'李四点点头。"
               "他们坐下来，张三点了一杯美式，李四要了拿铁。这是他们每周三的例行见面。"
    }).encode()

    req = urllib.request.Request(
        f"{API}/api/analyze/characters",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP错误 {e.code}: {body[:200]}")
        return False
    except Exception as e:
        print(f"  请求异常: {e}")
        return False

    d = json.loads(r.read())
    print(f"  code: {d['code']}")
    if d["code"] != 0:
        print(f"  message: {d.get('message', 'N/A')}")
        return False
    data = d.get("data")
    if not data:
        print(f"  data 为空")
        return False
    print(f"  角色数: {data.get('total', 'N/A')}")
    return True


def test_analyze_text_too_short():
    """文本太短：应触发 min_length 校验，返回 code=4001"""
    payload = json.dumps({"text": "太短了"}).encode()
    req = urllib.request.Request(
        f"{API}/api/analyze/characters",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        r = urllib.request.urlopen(req, timeout=10)
        d = json.loads(r.read())
        # FastAPI 的 RequestValidationError 被自定义处理器转为 200 + code=4001
        if d.get("code") == 4001:
            print(f"  ✅ 正确拦截：code={d['code']}, message={d.get('message','')[:60]}")
            return True
        else:
            print(f"  ❌ 未正确拦截：code={d.get('code')}, message={d.get('message','N/A')}")
            return False
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} - 期望 200 (body 含 code=4001)")
        body = e.read().decode()
        print(f"  body: {body[:200]}")
        return False
    except Exception as e:
        print(f"  请求异常: {e}")
        return False


# ── 主流程 ──
print("=" * 60)
print("PR11 测试：角色列表自动提取")
print("=" * 60)

if not check_server():
    print("\n❌ LLM 未就绪，跳过需要 API 的测试")
else:
    test("角色提取 - 正常请求（带标题）", test_analyze_characters)
    test("角色提取 - 无标题（可选字段）", test_analyze_no_title)

test("角色提取 - 文本太短（参数校验）", test_analyze_text_too_short)

print(f"\n{'=' * 60}")
print(f"测试结果: {pass_count} 通过, {fail_count} 失败")
print(f"{'=' * 60}")
