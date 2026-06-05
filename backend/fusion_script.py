"""
融合分析生成剧本
串联 PR11 角色提取 + PR12 场景提取 + PR13 对话分离，
将三阶段分析结果注入 Prompt，生成上下文更丰富的剧本
"""
from backend.character_extractor import extract_characters
from backend.scene_extractor import extract_scenes
from backend.dialogue_separator import extract_dialogue
from backend.llm_client import call_llm
from backend.version_prompts import get_version_prompt, VERSION_NAMES
from backend.yaml_parser import parse_yaml_to_script, script_to_yaml
from backend.yaml_validator import validate_and_fix_script, report_to_dict
from backend.errors import AppException, ErrorCode


def _build_fusion_user_prompt(
    text: str,
    title: str,
    version: str,
    chars: dict,
    scenes: dict,
    dialogue: dict,
    yaml_format_prompt: str = "",
) -> str:
    """构建融合分析后的 User Prompt，将提取的结构化信息注入上下文"""
    version_name = VERSION_NAMES.get(version, "电影版")
    parts = []

    # 0. YAML 格式指令（最前面，确保 LLM 知道输出格式）
    if yaml_format_prompt:
        parts.append(yaml_format_prompt)

    # 1. 角色档案
    parts.append("## 已分析角色档案\n")
    if chars.get("characters"):
        for c in chars["characters"]:
            role_tag = c.get("role_type", "未知")
            parts.append(
                f"- {c.get('name', '未知')}：{c.get('gender', '未知')}，"
                f"{c.get('age', '未知')}，{role_tag}"
            )
            if c.get("description"):
                parts.append(f"  {c.get('description', '')}")
        parts.append(f"\n共 {chars['total']} 个角色，角色分布：{chars.get('role_distribution', {})}")
    else:
        parts.append("(未提取到角色)")

    # 2. 场景地图
    parts.append("\n\n## 已分析场景地图\n")
    if scenes.get("scenes"):
        for s in scenes["scenes"]:
            parts.append(
                f"- 场景{s.get('scene_index', '?')}：{s.get('location', '未知')}"
                f" [{s.get('location_type', '未知')}] / {s.get('time_period', '未知')} / {s.get('weather', '未知')}"
            )
            if s.get("characters_present"):
                parts.append(f"  出场角色：{'、'.join(s['characters_present'])}")
            if s.get("description"):
                parts.append(f"  内容：{s['description']}")
        parts.append(f"\n共 {scenes['total']} 个场景")
        parts.append(f"场景分布：{scenes.get('location_distribution', {})}")
    else:
        parts.append("(未提取到场景)")

    # 3. 对话/叙述分析摘要
    parts.append("\n\n## 已分析文本结构\n")
    parts.append(f"总片段 {dialogue.get('total', 0)}：")
    parts.append(f"对话 {dialogue.get('dialogue_count', 0)} 条，叙述 {dialogue.get('narration_count', 0)} 段")
    parts.append(f"对话占比 {dialogue.get('dialogue_ratio', 0):.1%}")
    if dialogue.get("speaker_distribution"):
        speaker_list = sorted(
            dialogue["speaker_distribution"].items(),
            key=lambda x: x[1], reverse=True
        )
        parts.append(f"发言者排名：{'、'.join(f'{k}({v})' for k, v in speaker_list[:5])}")

    # 4. 原文
    parts.append(f"\n\n## 小说原文\n\n{text}\n")

    return "\n".join(parts)


def generate_fusion_script(text: str, title: str = "", version: str = "movie") -> dict:
    """融合分析后生成剧本

    执行流程：
    1. 提取角色信息 (PR11)
    2. 提取场景信息 (PR12)
    3. 分离对话与叙述 (PR13)
    4. 将三阶段分析结果 + 原文组装成增强版 Prompt
    5. 调用 LLM 生成剧本
    6. YAML 解析 + 验证修复

    Args:
        text: 小说原文
        title: 小说标题
        version: 剧本版本 (movie/tv_series/stage_play)

    Returns:
        {
            "title": str,
            "version": str,
            "text_length": int,
            "analysis": {
                "characters": {...},
                "scenes": {...},
                "dialogue": {...}
            },
            "script": {
                "yaml": str,
                "stats": {...},
                "validation": {...}
            }
        }
    """
    errors: list[str] = []

    # ── 步骤 1-3: 三阶段分析 ──
    chars = _safe_analyze("角色", lambda: extract_characters(text), errors)
    scenes = _safe_analyze("场景", lambda: extract_scenes(text), errors)
    dialogue = _safe_analyze("对话分离", lambda: extract_dialogue(text), errors)

    # ── 步骤 4: 组装增强 Prompt ──
    sys_prompt, yaml_format_prompt = get_version_prompt(version, title)
    fusion_user = _build_fusion_user_prompt(text, title, version, chars, scenes, dialogue, yaml_format_prompt)

    # ── 步骤 5: 调用 LLM ──
    raw_result = call_llm(sys_prompt, fusion_user)

    # ── 步骤 6: YAML 解析 + 验证修复 ──
    try:
        script_obj = parse_yaml_to_script(raw_result, source_title=title or "")
        fixed_script, validation_report = validate_and_fix_script(script_obj)
        script_yaml = script_to_yaml(fixed_script)
        script_stats = fixed_script.stats()
        validation = report_to_dict(validation_report)
        parse_warning = None
    except AppException:
        script_yaml = raw_result
        script_stats = None
        validation = None
        parse_warning = "YAML 解析失败，返回原始文本"

    return {
        "title": title or "未命名",
        "version": VERSION_NAMES.get(version, "电影版"),
        "text_length": len(text),
        "analysis": {
            "characters": chars,
            "scenes": scenes,
            "dialogue": dialogue,
        },
        "script": {
            "yaml": script_yaml,
            "stats": script_stats,
            "validation": validation,
            "parse_warning": parse_warning,
        },
        "analysis_errors": errors if errors else None,
    }


def _safe_analyze(label: str, fn, errors: list) -> dict:
    """安全执行分析步骤，失败时记录错误并返回空结构"""
    try:
        return fn()
    except Exception as e:
        errors.append(f"{label}分析失败: {str(e)[:100]}")
        return {}
