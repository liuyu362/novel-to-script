"""
融合分析生成剧本（全中文字段名）
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
    if chars.get("角色列表"):
        for c in chars["角色列表"]:
            role_tag = c.get("角色类型", "未知")
            alias = c.get("别名", [])
            alias_str = f"（别名：{'、'.join(alias)}）" if alias else ""
            parts.append(
                f"- {c.get('姓名', '未知')}：{c.get('性别', '未知')}，"
                f"{c.get('年龄', '未知')}，{role_tag} {alias_str}"
            )
            if c.get("描述"):
                parts.append(f"  {c.get('描述', '')}")
        parts.append(f"\n共 {chars['总数']} 个角色，角色分布：{chars.get('角色分布', {})}")
    else:
        parts.append("(未提取到角色)")

    # 2. 场景地图
    parts.append("\n\n## 已分析场景地图\n")
    if scenes.get("场景列表"):
        for s in scenes["场景列表"]:
            parts.append(
                f"- 场景{s.get('场景序号', '?')}：{s.get('地点', '未知')}"
                f" [{s.get('地点类型', '未知')}] / {s.get('时间段', '未知')} / {s.get('天气', '未知')}"
            )
            if s.get("在场角色"):
                parts.append(f"  出场角色：{'、'.join(s['在场角色'])}")
            if s.get("关键事件"):
                parts.append(f"  关键事件：{'、'.join(s['关键事件'])}")
            if s.get("描述"):
                parts.append(f"  内容：{s['描述']}")
        parts.append(f"\n共 {scenes['总数']} 个场景")
        parts.append(f"场景分布：{scenes.get('地点分布', {})}")
    else:
        parts.append("(未提取到场景)")

    # 3. 对话/叙述分析 — 注入统计 + 关键对话片段
    parts.append("\n\n## 已分析文本结构\n")
    parts.append(f"总片段 {dialogue.get('总数', 0)}：")
    parts.append(f"对话 {dialogue.get('对话数', 0)} 条，叙述 {dialogue.get('叙述数', 0)} 段")
    parts.append(f"对话占比 {dialogue.get('对话占比', 0):.1%}")
    if dialogue.get("发言者分布"):
        speaker_list = sorted(
            dialogue["发言者分布"].items(),
            key=lambda x: x[1], reverse=True
        )
        parts.append(f"发言者排名：{'、'.join(f'{k}({v})' for k, v in speaker_list[:5])}")

    # 注入关键对话片段（供 LLM 改写对白参考）
    segments = dialogue.get("片段列表", [])
    if segments:
        parts.append("\n\n### 关键对话片段（供改编对白参考）\n")
        # 只取前 40 条，防止 Prompt 过长
        for seg in segments[:40]:
            seg_type = seg.get("类型", "")
            if seg_type == "对话":
                speaker = seg.get("发言者", "未知")
                content = seg.get("内容", "")[:100]  # 截断长对话
                tone = seg.get("语气", "")
                tone_str = f"（{tone}）" if tone else ""
                parts.append(f"- [{speaker}]{tone_str}：{content}")
            elif seg_type == "叙述":
                content = seg.get("内容", "")[:100]
                parts.append(f"- [叙述]：{content}")
        if len(segments) > 40:
            parts.append(f"  ...（共 {len(segments)} 条片段，仅展示前 40 条）")

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
            "标题": str,
            "版本": str,
            "文本长度": int,
            "分析数据": {
                "角色分析": {...},
                "场景分析": {...},
                "对话分析": {...}
            },
            "剧本": {
                "yaml文本": str,
                "统计": {...},
                "验证": {...}
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
        "标题": title or "未命名",
        "版本": VERSION_NAMES.get(version, "电影版"),
        "文本长度": len(text),
        "分析数据": {
            "角色分析": chars,
            "场景分析": scenes,
            "对话分析": dialogue,
        },
        "剧本": {
            "yaml文本": script_yaml,
            "统计": script_stats,
            "验证": validation,
            "解析警告": parse_warning,
        },
        "分析错误": errors if errors else None,
    }


def _safe_analyze(label: str, fn, errors: list) -> dict:
    """安全执行分析步骤，失败时记录错误并返回空结构"""
    try:
        return fn()
    except Exception as e:
        errors.append(f"{label}分析失败: {str(e)[:100]}")
        return {}
