"""
PR12 测试: 场景/地点信息提取
验证 POST /api/analyze/scenes 端点
"""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

SAMPLE_TEXT = """夜幕降临，长安城的街道渐渐安静下来。

李青云推开茶馆的木门，一股暖意扑面而来。茶馆里只有零星几桌客人，角落里一个戴着斗笠的男人独自饮酒。

"小二，来壶龙井。"李青云在靠窗的位置坐下，目光不经意地扫过那个角落。

忽然，一道闪电划破夜空，紧接着雷声滚滚。暴雨倾盆而下，打在瓦片上噼啪作响。

戴斗笠的男人站起身，缓步走向门口。经过李青云桌边时，袖中滑出一封信，悄无声息地落在桌下。

次日清晨，雨过天晴。李青云踏着湿漉漉的青石板路，来到城东的醉仙楼。

二楼雅间里，一位白发老者早已等候多时。"你来了。"老者头也不抬地说。

"师父，"李青云躬身行礼，"弟子已经查到了线索。"

老者这才抬起头，锐利的目光穿透了清晨的薄雾。"说吧。" """


def test_scene_extraction():
    """测试场景提取端点"""
    print("=" * 50)
    print("PR12 测试: 场景/地点信息提取")
    print("=" * 50)

    # 1. 健康检查
    print("\n[1/5] 检查服务状态...")
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        data = resp.json()
        assert data["code"] == 0, f"健康检查失败: {data}"
        assert data["data"]["llm_ready"], "LLM 未就绪"
        print(f"  PASS: 服务正常, 模型={data['data']['llm_model']}")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    # 2. 调用场景提取
    print("\n[2/5] 调用 /api/analyze/scenes ...")
    resp = requests.post(
        f"{BASE_URL}/api/analyze/scenes",
        json={"text": SAMPLE_TEXT, "title": "测试-长安夜雨"},
        timeout=120,
    )
    data = resp.json()
    print(f"  code={data['code']}, message={data['message']}")

    assert data["code"] == 0, f"API 返回错误: {data}"
    result = data["data"]

    # 3. 验证场景数量
    print("\n[3/5] 验证场景数量...")
    total = result["total"]
    scenes = result["scenes"]
    print(f"  识别场景数: {total}")
    assert total >= 2, f"场景数太少，期望>=2，实际={total}"
    assert len(scenes) == total
    print(f"  PASS")

    # 4. 验证场景字段完整性
    print("\n[4/5] 验证场景字段...")
    required_fields = ["scene_index", "location", "location_type",
                       "time_period", "weather", "characters_present",
                       "description", "key_events"]
    for i, scene in enumerate(scenes):
        for field in required_fields:
            assert field in scene, f"场景{i+1}缺少字段: {field}"

        # scene_index 应连续
        assert scene["scene_index"] == i + 1, \
            f"场景{i+1} index 不连续: {scene['scene_index']}"

        # location_type 合法值
        assert scene["location_type"] in ("室内", "室外", "未知"), \
            f"场景{i+1} location_type 非法: {scene['location_type']}"

    print(f"  PASS: {total} 个场景字段完整")

    # 5. 验证分布统计
    print("\n[5/5] 验证分布统计...")
    loc_dist = result["location_distribution"]
    total_from_dist = sum(loc_dist.values())
    assert total_from_dist == total, \
        f"location_distribution 合计({total_from_dist}) != total({total})"

    all_locs = result["all_locations"]
    assert len(all_locs) == total, \
        f"all_locations 数量({len(all_locs)}) != total({total})"

    chars = result["all_characters_mentioned"]
    print(f"  地点分布: {loc_dist}")
    print(f"  所有地点: {all_locs}")
    print(f"  出场角色: {chars}")
    print(f"  PASS")

    # 展示场景详情
    print("\n" + "=" * 50)
    print("场景详情")
    print("=" * 50)
    for s in scenes:
        print(f"\n  场景{s['scene_index']}: {s['location']}")
        print(f"    类型: {s['location_type']} | 时间: {s['time_period']} | 天气: {s['weather']}")
        print(f"    角色: {', '.join(s['characters_present']) if s['characters_present'] else '无'}")
        print(f"    描述: {s['description']}")
        print(f"    事件: {', '.join(s['key_events']) if s['key_events'] else '无'}")

    print("\n" + "=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    test_scene_extraction()
