"""
综合解读模块
串联角色提取 + 场景提取 + 对话分离，一次性输出完整分析报告
"""
from backend.character_extractor import extract_characters
from backend.scene_extractor import extract_scenes
from backend.dialogue_separator import extract_dialogue


def analyze_novel(text: str) -> dict:
    """综合解读小说文本

    依次执行角色提取、场景提取、对话分离三阶段分析，
    汇总返回结构化的分析报告。

    Args:
        text: 小说原文内容

    Returns:
        {
            "characters": { ... },
            "scenes": { ... },
            "dialogue": { ... },
            "summary": { ... }
        }
    """
    chars = extract_characters(text)
    scenes = extract_scenes(text)
    dialogue = extract_dialogue(text)

    # 汇总摘要
    total_chars = chars.get("total", 0)
    total_scenes = scenes.get("total", 0)
    dialogue_count = dialogue.get("dialogue_count", 0)
    narration_count = dialogue.get("narration_count", 0)

    # 角色类型分布
    role_dist = chars.get("role_distribution", {})
    # 场景类型分布
    loc_dist = scenes.get("location_distribution", {})

    # 构建角色-场景关联：哪些角色在哪些场景出现
    scene_character_map = {}
    for sc in scenes.get("scenes", []):
        scene_idx = sc.get("scene_index", 0)
        scene_location = sc.get("location", "")
        scene_chars = sc.get("characters", [])
        if scene_chars:
            scene_character_map[str(scene_idx)] = {
                "location": scene_location,
                "characters": scene_chars,
            }

    return {
        "characters": chars,
        "scenes": scenes,
        "dialogue": dialogue,
        "summary": {
            "total_characters": total_chars,
            "total_scenes": total_scenes,
            "total_dialogues": dialogue_count,
            "total_narrations": narration_count,
            "dialogue_ratio": dialogue.get("dialogue_ratio", 0),
            "role_distribution": role_dist,
            "location_distribution": loc_dist,
            "scene_character_map": scene_character_map,
        },
    }
