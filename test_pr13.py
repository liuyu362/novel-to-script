"""
PR13 测试：对白与叙述文本分离
验证 POST /api/analyze/dialogue 端点
"""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

TEST_TEXT = """李青云推开茶馆的门，一股茶香扑面而来。

"客官，里面请！"小二热情地招呼着，一边用抹布擦了擦桌子。

李青云点了点头，在靠窗的位置坐下。窗外细雨绵绵，行人匆匆。

"来一壶龙井。"他淡淡说道，目光却始终没有离开街对面的那扇朱漆大门。

（那扇门后面，究竟藏着什么秘密？）他在心中暗自思忖。三年前的那个雨夜，师父就是从那扇门走进去，再也没有出来。

"客官，您的龙井。"小二端上茶壶，看着李青云的神色，小心翼翼地问，"客官是在等人？"

"算是吧。"李青云端起茶杯，嘴角露出一丝难以捉摸的笑意。"不过，不是我等他，是他在等我。" """


def test_health():
    """测试健康检查"""
    print("[TEST 1] 健康检查...")
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert data["code"] == 0, f"code={data['code']}, msg={data['message']}"
    assert data["data"]["status"] == "ok"
    print(f"  [OK] LLM状态: {data['data']['llm_ready']}")
    return True


def test_dialogue_separation():
    """测试对话分离"""
    print("\n[TEST 2] 对话分离...")
    r = requests.post(f"{BASE_URL}/api/analyze/dialogue", json={
        "text": TEST_TEXT,
        "title": "测试小说"
    })
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert data["code"] == 0, f"code={data['code']}, msg={data['message']}"

    result = data["data"]
    print(f"  [OK] 总片段: {result['total']}")
    print(f"  [OK] 对话数: {result['dialogue_count']}")
    print(f"  [OK] 叙述数: {result['narration_count']}")
    print(f"  [OK] 对话占比: {result['dialogue_ratio']}")
    print(f"  [OK] 发言者分布: {result['speaker_distribution']}")

    segments = result.get("segments", [])
    assert len(segments) > 0, "segments 为空"
    assert result["dialogue_count"] > 0, "没有识别到任何对话"
    assert result["narration_count"] > 0, "没有识别到任何叙述"

    # 验证片段结构
    for seg in segments:
        assert "type" in seg, f"片段缺少 type: {seg}"
        assert seg["type"] in ("dialogue", "narration"), f"非法 type: {seg['type']}"
        assert "content" in seg, f"片段缺少 content: {seg}"
        assert "index" in seg, f"片段缺少 index: {seg}"
        if seg["type"] == "dialogue":
            assert "speaker" in seg, f"对话缺少 speaker: {seg}"

    # 验证对话数+叙述数=总数
    assert result["dialogue_count"] + result["narration_count"] == result["total"], \
        f"对话+叙述 != 总数: {result['dialogue_count']}+{result['narration_count']}!={result['total']}"

    print(f"  [OK] 所有片段结构验证通过")
    return True


def test_empty_text():
    """测试空文本报错"""
    print("\n[TEST 3] 空文本处理...")
    r = requests.post(f"{BASE_URL}/api/analyze/dialogue", json={
        "text": "",
        "title": "空"
    })
    data = r.json()
    assert data["code"] != 0, f"空文本应报错，实际 code={data['code']}"
    print(f"  [OK] 正确拒绝空文本: {data['message']}")
    return True


def test_short_text():
    """测试极短文本不会崩溃"""
    print("\n[TEST 4] 极短文本处理...")
    r = requests.post(f"{BASE_URL}/api/analyze/dialogue", json={
        "text": '他推开门，雨丝飘进屋内。"你好，欢迎光临！"小二热情地说道。李青云点了点头，在靠窗位置坐下，目光却始终没有离开街对面那扇朱漆大门。',
        "title": "极短"
    })
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert data["code"] == 0, f"极短文本不应报错: code={data['code']}, msg={data['message']}"
    result = data["data"]
    print(f"  [OK] 总片段: {result['total']}, 对话: {result['dialogue_count']}, 叙述: {result['narration_count']}")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("PR13 测试：对白与叙述文本分离")
    print("=" * 50)

    passed = 0
    failed = 0

    tests = [
        ("健康检查", test_health),
        ("对话分离", test_dialogue_separation),
        ("空文本处理", test_empty_text),
        ("极短文本处理", test_short_text),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  [FAIL] {name}: {e}")

    print("\n" + "=" * 50)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 50)

    sys.exit(0 if failed == 0 else 1)
