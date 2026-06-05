"""
综合解读模块（全中文字段名）
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
            "角色分析": { ... },
            "场景分析": { ... },
            "对话分析": { ... },
            "汇总": { ... }
        }
    """
    chars = extract_characters(text)
    scenes = extract_scenes(text)
    dialogue = extract_dialogue(text)

    # 汇总摘要
    total_chars = chars.get("总数", 0)
    total_scenes = scenes.get("总数", 0)
    dialogue_count = dialogue.get("对话数", 0)
    narration_count = dialogue.get("叙述数", 0)

    # 角色类型分布
    role_dist = chars.get("角色分布", {})
    # 场景类型分布
    loc_dist = scenes.get("地点分布", {})

    # 构建角色-场景关联：哪些角色在哪些场景出现
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
