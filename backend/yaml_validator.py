"""
YAML 格式验证器与自动修复
验证 LLM 输出的 YAML 数据是否完整、合法，对常见问题自动修复

设计原则：
- 验证但不阻断：能修复的问题自动修复，不能修复的标记为 warning
- 降级优先：数据不完美也能工作，宁可部分缺失也不崩溃
- 透明报告：所有修改都记录在报告中，用户可追溯
"""

from dataclasses import dataclass, field
from typing import Any

from backend.schema import Script, Meta, Character, Scene, Act

# ─── 合法值定义 ─────────────────────────────

VALID_VERSIONS = {"movie", "tv_series", "stage_play"}
VALID_ACT_TYPES = {"action", "dialogue", "direction"}
VALID_EMOTIONS = {
    "平静", "愤怒", "悲伤", "喜悦", "紧张",
    "恐惧", "嘲讽", "温柔", "惊讶", "无奈", "坚定", "犹豫", "",
}
VALID_ROLE_TYPES = {"主角", "配角", "反派", "路人", "其他", ""}
VALID_GENDERS = {"男", "女", "不详", ""}


# ─── 数据类 ─────────────────────────────────

@dataclass
class ValidationIssue:
    """单个验证问题"""
    field: str       # 字段路径，如 "meta.title"
    severity: str    # "error" | "warning" | "fixed"
    message: str


@dataclass
class ValidationReport:
    """验证报告"""
    is_valid: bool                          # 整体是否通过（warning 不影响 is_valid）
    issues: list[ValidationIssue] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)


# ─── 辅助函数 ───────────────────────────────

def _safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_list(val):
    return val if isinstance(val, list) else []


# ─── 核心验证 ───────────────────────────────

def validate_and_fix_script(script: Script) -> tuple[Script, ValidationReport]:
    """验证并自动修复 Script 对象

    返回修复后的 Script 和验证报告。
    不抛出异常——即使数据有问题也会尽力修复。
    """
    report = ValidationReport(is_valid=True)

    # ── 1. 验证 Meta ──
    meta = script.meta

    if not meta.title or meta.title == "未命名剧本":
        meta.title = meta.source_title + "·剧本" if meta.source_title else "未命名剧本"
        report.fixes_applied.append(f"meta.title → '{meta.title}'")

    if meta.version not in VALID_VERSIONS:
        old = meta.version
        meta.version = "movie"
        report.fixes_applied.append(f"meta.version: '{old}' → 'movie'")
        report.issues.append(ValidationIssue(
            "meta.version", "fixed", f"版本值无效 '{old}'，默认改为 movie"
        ))

    if not meta.source_title and meta.title:
        meta.source_title = meta.title.replace("·剧本", "").replace(".电影版", "")

    # ── 2. 验证 Characters ──
    valid_characters = []
    for i, char in enumerate(script.characters):
        if not char.name:
            report.issues.append(ValidationIssue(
                f"characters[{i}]", "warning", f"角色 #{i+1} 缺少名称，已跳过"
            ))
            continue

        # 修复 ID
        if not char.id:
            char.id = i + 1
            report.fixes_applied.append(f"character[{i}].id → {char.id}")

        # 修复性别
        if char.gender not in VALID_GENDERS:
            report.issues.append(ValidationIssue(
                f"characters[{i}].gender", "fixed",
                f"性别值无效 '{char.gender}'，已清空"
            ))
            char.gender = ""

        # 修复角色类型
        if char.role_type not in VALID_ROLE_TYPES:
            report.issues.append(ValidationIssue(
                f"characters[{i}].role_type", "fixed",
                f"角色类型无效 '{char.role_type}'，已清空"
            ))
            char.role_type = ""

        # 确保 aliases 是列表
        if not isinstance(char.aliases, list):
            char.aliases = []

        # first_appearance
        if not char.first_appearance:
            char.first_appearance = 1

        valid_characters.append(char)

    script.characters = valid_characters
    script.meta.character_count = len(valid_characters)

    # ── 3. 验证 Scenes ──
    if not script.scenes:
        report.is_valid = False
        report.issues.append(ValidationIssue(
            "scenes", "error", "剧本中没有场景数据"
        ))
        return script, report

    valid_scenes = []
    for i, scene in enumerate(script.scenes):
        # 修复场景 ID
        if not scene.id:
            scene.id = i + 1
            report.fixes_applied.append(f"scene[{i}].id → {scene.id}")

        # 修复场景名
        if not scene.name:
            scene.name = f"场景{scene.id}"
            report.issues.append(ValidationIssue(
                f"scenes[{i}].name", "warning", "场景名缺失，使用默认名"
            ))

        # 确保选项字段存在
        for field in ["location", "time", "weather"]:
            if not getattr(scene, field, None):
                setattr(scene, field, "")

        # 确保 characters 是列表
        if not isinstance(scene.characters, list):
            scene.characters = []

        # ── 3a. 验证 Acts ──
        valid_acts = []
        for j, act in enumerate(scene.acts):
            # 修复 act 类型
            if act.type not in VALID_ACT_TYPES:
                old_type = act.type
                act.type = "action"
                report.fixes_applied.append(
                    f"scene[{i}].act[{j}].type: '{old_type}' → 'action'"
                )
                report.issues.append(ValidationIssue(
                    f"scenes[{i}].acts[{j}].type", "fixed",
                    f"act 类型无效 '{old_type}'，改为 action"
                ))

            # 内容为空则跳过
            if not act.content:
                report.issues.append(ValidationIssue(
                    f"scenes[{i}].acts[{j}]", "warning", "act 内容为空，已跳过"
                ))
                continue

            # dialogue 和 action 必须有关联角色
            if act.type in ("dialogue", "action") and not act.character:
                report.issues.append(ValidationIssue(
                    f"scenes[{i}].acts[{j}].character", "warning",
                    f"act 类型为 '{act.type}' 但缺失角色名"
                ))

            # emotion 可选，确保存在
            if not act.emotion:
                act.emotion = ""

            # note 可选
            if not act.note:
                act.note = ""

            valid_acts.append(act)

        scene.acts = valid_acts
        valid_scenes.append(scene)

    script.scenes = valid_scenes
    script.meta.total_scenes = len(valid_scenes)

    # 最终检查
    if not valid_scenes:
        report.is_valid = False
        report.issues.append(ValidationIssue(
            "scenes", "error", "没有有效场景数据（所有场景的 act 均为空）"
        ))

    return script, report


def report_to_dict(report: ValidationReport) -> dict:
    """将验证报告转为字典，供 API 返回"""
    return {
        "is_valid": report.is_valid,
        "issues": [
            {"field": i.field, "severity": i.severity, "message": i.message}
            for i in report.issues
        ],
        "fixes_applied": report.fixes_applied,
        "total_issues": len(report.issues),
        "total_fixes": len(report.fixes_applied),
    }
