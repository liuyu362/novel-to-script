"""
PR16 测试: 综合解读端点 /api/analyze/novel
"""
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

SAMPLE_TEXT = (
    "长安城的清晨笼罩在一层薄雾之中。茶馆里，小二擦拭着柜台，门口风铃轻响。"
    "一位身着青衫的中年文士推门而入，目光如电，扫视了一圈在座的茶客。"
    "\"来一壶龙井。\"他淡淡开口，声音不大却让整个茶馆安静了一瞬。"
    "小二愣了一下，连忙应道：\"好嘞，客官稍等！\""
    "角落里，一位白发老者抬起浑浊的双眼，嘴角露出一丝若有若无的笑意。"
    "\"李青云，十年不见，你还是这副急性子。\""
    "那文士——李青云——身形一顿，缓缓转身，拱手道：\"陈伯，别来无恙。\""
)

SHORT_TEXT = "他推开门，细雨飘进屋内。小二迎上前去。李青云在靠窗位置坐下。茶馆里茶客寥寥，窗外青石板路被雨水打湿。"

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


def check_response(resp):
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 0, f"code={data['code']}, message={data.get('message')}"
    return data["data"]


# ── 发送一次综合解读，后续测试复用，避免重复 LLM 调用 ──
print("正在调用综合解读接口（含角色+场景+对话三次 LLM 调用）...")
resp = requests.post(
    f"{BASE_URL}/api/analyze/novel",
    json={"text": SAMPLE_TEXT, "title": "测试小说"},
    timeout=120,
)
full_data = check_response(resp)


print("\n1. 综合解读响应结构")
test("状态码 200 + code == 0", lambda: None)  # 已在上面 check_response 验证


def _check_characters():
    assert "characters" in full_data, f"缺少 characters，现有: {list(full_data.keys())}"
test("包含 characters 字段", _check_characters)


def _check_scenes():
    assert "scenes" in full_data
test("包含 scenes 字段", _check_scenes)


def _check_dialogue():
    assert "dialogue" in full_data
test("包含 dialogue 字段", _check_dialogue)


def _check_summary():
    assert "summary" in full_data
    s = full_data["summary"]
    assert isinstance(s.get("total_characters"), int)
test("包含 summary 摘要", _check_summary)


def _check_summary_fields():
    s = full_data["summary"]
    for key in ["total_characters", "total_scenes", "total_dialogues", "total_narrations", "dialogue_ratio"]:
        assert key in s, f"缺少字段 {key}"
test("summary 统计字段完整", _check_summary_fields)


print("\n2. 超短文本（刚好50字符）")
test("短文本正常响应", lambda: check_response(
    requests.post(f"{BASE_URL}/api/analyze/novel", json={"text": SHORT_TEXT}, timeout=120)
))


print("\n3. 无效请求")
# 注：app 的 validation_exception_handler 将 422 转为 HTTP 200
# 需通过 body.code != 0 判断参数校验失败
def _empty_text():
    r = requests.post(f"{BASE_URL}/api/analyze/novel", json={"text": ""})
    assert r.status_code == 200, f"期望200，实际{r.status_code}"
    data = r.json()
    assert data["code"] != 0, f"空文本应返回错误码，实际 code={data['code']}"
test("空文本返回错误码", _empty_text)


def _too_short_text():
    r = requests.post(f"{BASE_URL}/api/analyze/novel", json={"text": "一句话"})
    assert r.status_code == 200, f"期望200，实际{r.status_code}"
    data = r.json()
    assert data["code"] != 0, f"过短文本应返回错误码，实际 code={data['code']}"
test("过短文本返回错误码", _too_short_text)


print(f"\n{'='*40}")
print(f"通过: {PASS} / 失败: {FAIL}")
if FAIL > 0:
    sys.exit(1)
