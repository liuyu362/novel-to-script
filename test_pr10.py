"""
PR10 测试：多版本 Prompt
"""
import sys
sys.path.insert(0, "F:/七牛云议题/novel-to-script")

from backend.version_prompts import (
    build_versioned_yaml_prompt, get_version_prompt,
    VERSION_NAMES, VALID_VERSIONS, VERSION_YAML_PROMPTS,
)

# Test 1: Valid versions
print("=" * 60)
print("[TEST 1] verify valid versions")
assert VALID_VERSIONS == ["movie", "tv_series", "stage_play"], f"Got: {VALID_VERSIONS}"
print(f"  VALID_VERSIONS: {VALID_VERSIONS}")

# Test 2: Version names
print("\n" + "=" * 60)
print("[TEST 2] verify version names")
for v in VALID_VERSIONS:
    assert v in VERSION_NAMES
    print(f"  {v} -> {VERSION_NAMES[v]}")

# Test 3: build_versioned_yaml_prompt for each version
print("\n" + "=" * 60)
print("[TEST 3] build_versioned_yaml_prompt")
test_text = "夜深了，李明坐在昏暗的房间里。"
for v in VALID_VERSIONS:
    sys_prompt, user_prompt = build_versioned_yaml_prompt(v, test_text, "测试小说")
    assert len(sys_prompt) > 50, f"sys_prompt too short for {v}"
    assert "测试小说" in user_prompt, f"title not in user_prompt for {v}"
    assert v in user_prompt, f"version '{v}' not in prompt"
    print(f"  [{v}] sys_prompt: {len(sys_prompt)} chars, user_prompt: {len(user_prompt)} chars")

# Test 4: get_version_prompt
print("\n" + "=" * 60)
print("[TEST 4] get_version_prompt")
for v in VALID_VERSIONS:
    sys_prompt, yaml_prompt = get_version_prompt(v, "测试")
    assert len(sys_prompt) > 20, f"sys_prompt too short for {v}"
    assert "测试" in yaml_prompt, f"title not in yaml_prompt for {v}"
    print(f"  [{v}] yaml_prompt: {len(yaml_prompt)} chars")

# Test 5: invalid version defaults to movie
print("\n" + "=" * 60)
print("[TEST 5] invalid version defaults to movie")
sys_prompt, yaml_prompt = get_version_prompt("invalid", "测试")
assert "movie" in yaml_prompt.lower() or "电影" in yaml_prompt
print(f"  fallback to movie: OK")

# Test 6: version-specific keywords in prompts
print("\n" + "=" * 60)
print("[TEST 6] version-specific keywords")
_, movie_p = get_version_prompt("movie", "测试")
_, tv_p = get_version_prompt("tv_series", "测试")
_, stage_p = get_version_prompt("stage_play", "测试")

assert "紧凑节奏" in movie_p or "视觉化" in movie_p, "movie keywords missing"
assert "多集分季" in tv_p or "成长弧线" in tv_p, "tv keywords missing"
assert "有限场景" in stage_p or "对话冲突" in stage_p, "stage keywords missing"
print("  movie prompt contains version-specific keywords: OK")
print("  tv_series prompt contains version-specific keywords: OK")
print("  stage_play prompt contains version-specific keywords: OK")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
