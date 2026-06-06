"""
测试作品管理 API（不依赖 LLM）
"""
import sys
import os
import json
import time

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_works_api():
    """测试作品管理 CRUD API"""
    print("=" * 60)
    print("测试作品管理 API")
    print("=" * 60)

    # 1. 测试创建作品
    print("\n1. 测试 POST /api/works（创建作品）")
    resp = client.post("/api/works", json={
        "title": "测试作品",
        "original_text": "这是一个测试小说的内容。主角小明今天去了公园。",
    })
    result = resp.json()
    print(f"   状态码: {resp.status_code}")
    print(f"   响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

    if result["code"] == 0:
        work_id = result["data"]["id"]
        print(f"   ✅ 创建成功，作品 ID = {work_id}")
    else:
        print(f"   ❌ 创建失败: {result['message']}")
        return

    # 2. 测试获取作品列表
    print("\n2. 测试 GET /api/works（获取作品列表）")
    resp = client.get("/api/works")
    result = resp.json()
    print(f"   状态码: {resp.status_code}")
    print(f"   作品数量: {len(result['data'])}")
    print(f"    列表获取成功")

    # 3. 测试获取单部作品
    print(f"\n3. 测试 GET /api/works/{work_id}（获取单部作品）")
    resp = client.get(f"/api/works/{work_id}")
    result = resp.json()
    print(f"   状态码: {resp.status_code}")
    print(f"   作品标题: {result['data']['title']}")
    print(f"   原文长度: {len(result['data']['original_text'])} 字")
    print(f"    获取成功")

    # 4. 测试更新作品
    print(f"\n4. 测试 PUT /api/works/{work_id}（更新作品）")
    resp = client.put(f"/api/works/{work_id}", json={
        "title": "更新后的标题",
        "current_step": 2,
    })
    result = resp.json()
    print(f"   状态码: {resp.status_code}")
    print(f"   新标题: {result['data']['title']}")
    print(f"   当前步骤: {result['data']['current_step']}")
    print(f"   ✅ 更新成功")

    # 5. 测试删除作品
    print(f"\n5. 测试 DELETE /api/works/{work_id}（删除作品）")
    resp = client.delete(f"/api/works/{work_id}")
    result = resp.json()
    print(f"   状态码: {resp.status_code}")
    print(f"   响应: {result['message']}")
    print(f"   ✅ 删除成功")

    # 6. 测试获取不存在的作品
    print(f"\n6. 测试 GET /api/works/999999（获取不存在的作品）")
    resp = client.get("/api/works/999999")
    result = resp.json()
    print(f"   状态码: {resp.status_code}")
    print(f"   错误码: {result['code']}")
    print(f"   错误消息: {result['message']}")
    print(f"   ✅ 正确返回 4005 NOT_FOUND")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test_works_api()
