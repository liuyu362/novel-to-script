"""
PR14 测试：融合分析生成剧本
验证 POST /api/convert/fusion 端点
"""
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

TEST_TEXT = """李青云推开茶馆的门，一股茶香扑面而来。

"客官，里面请！"小二热情地招呼着，一边用抹布擦了擦桌子。

李青云点了点头，在靠窗的位置坐下。窗外细雨绵绵，行人匆匆。

"来一壶龙井。"他淡淡说道，目光却始终没有离开街对面的那扇朱漆大门。

（那扇门后面，究竟藏着什么秘密？）他在心中暗自思忖。三年前的那个雨夜，师父就是从那扇门走进去，再也没有出来。

"客官，您的龙井。"小二端上茶壶，看着李青云的神色，小心翼翼地问，"客官是在等人？"

"算是吧。"李青云端起茶杯，嘴角露出一丝难以捉摸的笑意。"不过，不是我等他，是他在等我。"

话音刚落，街对面那扇朱漆大门突然打开了一条缝。一道黑影从中闪出，随即消失在雨幕中。李青云瞳孔微缩，茶杯停在半空。"""


def test_health():
    """健康检查"""
    print("[TEST 1] 健康检查...")
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    print(f"  [OK] LLM: {data['data']['llm_ready']}")
    return True


def test_fusion_convert_movie():
    """融合转换 - 电影版"""
    print("\n[TEST 2] 融合转换（电影版）...")
    r = requests.post(f"{BASE_URL}/api/convert/fusion", json={
        "text": TEST_TEXT,
        "title": "测试小说",
        "version": "movie"
    }, timeout=180)
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert data["code"] == 0, f"code={data['code']}, msg={data['message']}"

    result = data["data"]
    assert "analysis" in result
    assert "script" in result

    # 验证分析数据
    analysis = result["analysis"]
    chars = analysis["characters"]
    scenes = analysis["scenes"]
    dialogue = analysis["dialogue"]

    print(f"  [OK] 角色: {chars.get('total', 0)} 个")
    print(f"  [OK] 场景: {scenes.get('total', 0)} 个")
    print(f"  [OK] 对话: {dialogue.get('dialogue_count', 0)} 条 / 叙述: {dialogue.get('narration_count', 0)} 段")
    print(f"  [OK] 版本: {result['version']}")

    # 验证剧本数据
    script = result["script"]
    assert "yaml" in script
    assert len(script["yaml"]) > 50, f"剧本太短 ({len(script['yaml'])} 字符)"
    print(f"  [OK] 剧本长度: {len(script['yaml'])} 字符")

    if script.get("stats"):
        stats = script["stats"]
        print(f"  [OK] 剧本统计: {stats.get('scene_count', 0)} 场景, {stats.get('character_count', 0)} 角色")
    if script.get("parse_warning"):
        print(f"  [WARN] {script['parse_warning']}")

    return True


def test_fusion_convert_tv():
    """融合转换 - 电视剧版"""
    print("\n[TEST 3] 融合转换（电视剧版）...")
    r = requests.post(f"{BASE_URL}/api/convert/fusion", json={
        "text": TEST_TEXT,
        "title": "测试小说",
        "version": "tv_series"
    }, timeout=180)
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0

    result = data["data"]
    assert result["version"] == "电视剧版"
    assert len(result["script"]["yaml"]) > 50
    print(f"  [OK] 版本: {result['version']}, 剧本: {len(result['script']['yaml'])} 字符")
    return True


def test_empty_text():
    """空文本处理"""
    print("\n[TEST 4] 空文本处理...")
    r = requests.post(f"{BASE_URL}/api/convert/fusion", json={
        "text": "",
        "title": "空"
    })
    data = r.json()
    assert data["code"] != 0, f"空文本应报错, code={data['code']}"
    print(f"  [OK] 正确拒绝: {data['message']}")
    return True


def test_invalid_version():
    """非法版本回退"""
    print("\n[TEST 5] 非法版本回退...")
    r = requests.post(f"{BASE_URL}/api/convert/fusion", json={
        "text": TEST_TEXT,
        "title": "测试",
        "version": "invalid"
    }, timeout=180)
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    assert data["data"]["version"] == "电影版", f"应回退电影版, 实际: {data['data']['version']}"
    print(f"  [OK] 非法版本自动回退: {data['data']['version']}")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("PR14 测试：融合分析生成剧本")
    print("=" * 50)

    passed = 0
    failed = 0

    tests = [
        ("健康检查", test_health),
        ("融合转换-电影版", test_fusion_convert_movie),
        ("融合转换-电视剧版", test_fusion_convert_tv),
        ("空文本处理", test_empty_text),
        ("非法版本回退", test_invalid_version),
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
