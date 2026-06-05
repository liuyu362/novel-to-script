"""
综合解读模块（全中文字段名）
串联角色提取 + 场景提取 + 对话分离
支持全文一次性分析 或 按章节逐章分析后合并
"""
from backend.character_extractor import extract_characters
from backend.scene_extractor import extract_scenes
from backend.dialogue_separator import extract_dialogue
from backend.chapter_splitter import split_chapters, split_by_length, detect_chapter_pattern
from typing import Optional


def analyze_novel(text: str, chapter_wise: bool = True, max_chars_per_chapter: int = 8000) -> dict:
    """综合解读小说文本

     Args:
        text: 小说原文内容
        chapter_wise: 是否按章节逐章分析（True=分章处理，False=全文一次性处理）
        max_chars_per_chapter: 分章模式下每章最大字数（超过则再分割）

    Returns:
        {
            "角色分析": { ... },
            "场景分析": { ... },
            "对话分析": { ... },
            "汇总": { ... },
            "分章信息": { ... }   # 仅 chapter_wise=True 时有内容
        }
    """
    if chapter_wise and len(text) > max_chars_per_chapter:
        return _analyze_by_chapters(text, max_chars_per_chapter)
    else:
        return _analyze_full(text)


def _analyze_full(text: str) -> dict:
    """全文一次性分析（原有逻辑）"""
    chars = extract_characters(text)
    scenes = extract_scenes(text)
    dialogue = extract_dialogue(text)
    return _build_result(chars, scenes, dialogue)


def _analyze_by_chapters(text: str, max_chars_per_chapter: int) -> dict:
    """按章节逐章分析，然后合并结果"""

    # 1. 尝试按章节标题分割
    pattern = detect_chapter_pattern(text)
    if pattern:
        split_result = split_chapters(text, pattern_override=pattern)
        chapters = split_result.chapters
        pattern_used = split_result.pattern_used
    else:
        # 无章节标题 → 按字数强制分割
        chapters = split_by_length(text, max_chars_per_chapter)
        pattern_used = "字数分割"

    if not chapters:
        # 兜底：全文分析
        return _analyze_full(text)

    # 2. 逐章调用分析
    all_char_results = []
    all_scene_results = []
    all_dialogue_results = []
    chapter_infos = []

    for i, ch in enumerate(chapters):
        ch_text = ch.content
        if not ch_text.strip():
            continue

        # 调用三个分析函数
        try:
            ch_chars = extract_characters(ch_text)
        except Exception:
            ch_chars = {"角色列表": [], "总数": 0, "角色分布": {}}
        try:
            ch_scenes = extract_scenes(ch_text)
        except Exception:
            ch_scenes = {"场景列表": [], "总数": 0, "地点分布": {}, "所有地点": []}
        try:
            ch_dialogue = extract_dialogue(ch_text)
        except Exception:
            ch_dialogue = {"片段列表": [], "总数": 0, "对话数": 0, "叙述数": 0, "发言者分布": {}}

        all_char_results.append(ch_chars)
        all_scene_results.append(ch_scenes)
        all_dialogue_results.append(ch_dialogue)
        chapter_infos.append({
            "序号": ch.index,
            "标题": ch.title,
            "字数": len(ch_text),
        })

    # 3. 合并结果
    merged_chars = _merge_characters(all_char_results)
    merged_scenes = _merge_scenes(all_scene_results)
    merged_dialogue = _merge_dialogue(all_dialogue_results, all_char_results)

    result = _build_result(merged_chars, merged_scenes, merged_dialogue)
    result["分章信息"] = {
        "章节模式": pattern_used,
        "章节数": len(chapter_infos),
        "章节列表": chapter_infos,
    }
    return result


# ── 角色合并 ───────────────────────────────────────────────────────────────────

ROLE_ORDER = {"路人": 0, "配角": 1, "反派": 1, "主角": 2}

def _merge_characters(chapter_results: list[dict]) -> dict:
    """合并多章的角色提取结果

    策略：
    - 按「姓名」去重
    - 别名取并集
    - 角色类型取最高级（主角 > 反派/配角 > 路人）
    - 描述/性别/年龄：优先取非空，类型高级优先
    """
    merged = {}  # name -> char dict

    for res in chapter_results:
        for char in res.get("角色列表", []):
            name = char.get("姓名", "").strip()
            if not name:
                continue

            if name not in merged:
                merged[name] = dict(char)
                merged[name]["_seen"] = True
            else:
                # 合并别名
                existing_aliases = set(merged[name].get("别名", []))
                for alias in char.get("别名", []):
                    if alias not in existing_aliases:
                        merged[name]["别名"].append(alias)
                        existing_aliases.add(alias)

                # 升级角色类型
                cur_role = merged[name].get("角色类型", "路人")
                new_role = char.get("角色类型", "路人")
                if ROLE_ORDER.get(new_role, 0) > ROLE_ORDER.get(cur_role, 0):
                    merged[name]["角色类型"] = new_role

                # 优先保留有描述的
                if not merged[name].get("描述", "").strip() and char.get("描述", "").strip():
                    merged[name]["描述"] = char["描述"]

                # 性别/年龄：优先取非空
                for field in ("性别", "年龄"):
                    if merged[name].get(field, "") in ("", "未知") and char.get(field, "") not in ("", "未知"):
                        merged[name][field] = char[field]

    # 重新编号
    char_list = list(merged.values())
    for i, ch in enumerate(char_list, 1):
        ch["编号"] = i
        ch.pop("_seen", None)

    # 重新计算分布
    role_dist = {}
    for ch in char_list:
        role = ch.get("角色类型", "路人")
        role_dist[role] = role_dist.get(role, 0) + 1

    return {
        "角色列表": char_list,
        "总数": len(char_list),
        "角色分布": role_dist,
    }


# ── 场景合并 ───────────────────────────────────────────────────────────────────

def _merge_scenes(chapter_results: list[dict]) -> dict:
    """合并多章的场景提取结果，全局重编号"""
    all_scenes = []
    all_locations = set()
    loc_dist = {}

    global_idx = 0
    for res in chapter_results:
        for sc in res.get("场景列表", []):
            global_idx += 1
            sc = dict(sc)
            sc["场景序号"] = global_idx
            all_scenes.append(sc)

            # 合并地点
            loc = sc.get("地点", "")
            if loc:
                all_locations.add(loc)
                loc_type = sc.get("地点类型", "未知")
                loc_dist[loc_type] = loc_dist.get(loc_type, 0) + 1

    return {
        "场景列表": all_scenes,
        "总数": len(all_scenes),
        "地点分布": loc_dist,
        "所有地点": sorted(all_locations),
        "所有提及角色": _collect_all_chars(all_scenes),
    }


def _collect_all_chars(scenes: list[dict]) -> list[str]:
    chars = set()
    for sc in scenes:
        for c in sc.get("在场角色", []):
            chars.add(c)
    return sorted(chars)


# ── 对话合并 ───────────────────────────────────────────────────────────────────

def _merge_dialogue(chapter_results: list[dict], char_results: list[dict]) -> dict:
    """合并多章的对话分离结果，全局重编号"""
    all_segments = []
    speaker_dist = {}
    dialogue_count = 0
    narration_count = 0
    global_idx = 0

    for res in chapter_results:
        for seg in res.get("片段列表", []):
            global_idx += 1
            seg = dict(seg)
            seg["序号"] = global_idx
            all_segments.append(seg)

            # 统计
            if seg.get("类型") == "对话":
                dialogue_count += 1
                speaker = seg.get("发言者", "未知")
                speaker_dist[speaker] = speaker_dist.get(speaker, 0) + 1
            else:
                narration_count += 1

    total = dialogue_count + narration_count
    ratio = round(dialogue_count / total, 3) if total > 0 else 0

    return {
        "片段列表": all_segments,
        "总数": total,
        "对话数": dialogue_count,
        "叙述数": narration_count,
        "对话占比": ratio,
        "发言者分布": speaker_dist,
    }


# ── 结果组装 ───────────────────────────────────────────────────────────────────

def _build_result(chars: dict, scenes: dict, dialogue: dict) -> dict:
    """组装最终结果"""
    total_chars = chars.get("总数", 0)
    total_scenes = scenes.get("总数", 0)
    dialogue_count = dialogue.get("对话数", 0)
    narration_count = dialogue.get("叙述数", 0)

    role_dist = chars.get("角色分布", {})
    loc_dist = scenes.get("地点分布", {})

    # 构建角色-场景关联
    scene_character_map = {}
    for sc in scenes.get("场景列表", []):
        scene_idx = sc.get("场景序号", 0)
        scene_location = sc.get("地点", "")
        scene_chars = sc.get("在场角色", [])
        if scene_chars:
            scene_character_map[str(scene_idx)] = {
                "地点": scene_location,
                "角色": scene_chars,
            }

    return {
        "角色分析": chars,
        "场景分析": scenes,
        "对话分析": dialogue,
        "汇总": {
            "角色总数": total_chars,
            "场景总数": total_scenes,
            "对话总数": dialogue_count,
            "叙述总数": narration_count,
            "对话占比": dialogue.get("对话占比", 0),
            "角色分布": role_dist,
            "地点分布": loc_dist,
            "角色场景关联": scene_character_map,
        },
    }
