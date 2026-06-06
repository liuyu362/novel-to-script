"""
YAML 格式验证器与自动修复（全中文字段名）
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

VALID_VERSIONS = {"电影版", "电视剧版", "舞台剧版"}
VALID_ACT_TYPES = {"动作", "对白", "导演指示"}
VALID_EMOTIONS = {
    "平静", "愤怒", "悲伤", "喜悦", "紧张",
    "恐惧", "嘲讽", "温柔", "惊讶", "无奈", "坚定", "犹豫", "",
}
VALID_ROLE_TYPES = {"主角", "配角", "反派", "路人", "其他", ""}
VALID_GENDERS = {"男", "女", "不详", ""}

# ─── v2.1 新增合法值定义 ─────────────────────
VALID_SHOT_SIZES = {"远景", "全景", "中景", "近景", "特写", "大特写", ""}
VALID_ANGLES = {"平视", "俯视", "仰视", "鸟瞰", "倾斜", ""}
VALID_MOVEMENTS = {"固定", "推", "拉", "摇", "移", "跟", "升降", "手持", ""}
VALID_TRANSITIONS = {"切至", "淡入淡出", "淡入", "淡出", "叠化", "划像", "黑场", ""}
VALID_SLUGLINE_INDICATORS = {"内景", "外景", "内景/外景"}


# ─── 数据类 ─────────────────────────────────

@dataclass
class ValidationIssue:
    """单个验证问题"""
    field: str       # 字段路径，如 "元信息.标题"
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

    # ── 1. 验证 元信息 ──
    meta = script.元信息

    if not meta.标题 or meta.标题 == "未命名剧本":
        meta.标题 = meta.原著作 + "·剧本" if meta.原著作 else "未命名剧本"
        report.fixes_applied.append(f"元信息.标题 → '{meta.标题}'")

    if meta.版本 not in VALID_VERSIONS:
        old = meta.版本
        meta.版本 = "电影版"
        report.fixes_applied.append(f"元信息.版本: '{old}' → '电影版'")
        report.issues.append(ValidationIssue(
            "元信息.版本", "fixed", f"版本值无效 '{old}'，默认改为 电影版"
        ))

    if not meta.原著作 and meta.标题:
        meta.原著作 = meta.标题.replace("·剧本", "").replace(".电影版", "").replace(".电视剧版", "").replace(".舞台剧版", "")

    # ── 2. 验证 角色列表 ──
    valid_characters = []
    for i, char in enumerate(script.角色列表):
        if not char.姓名:
            report.issues.append(ValidationIssue(
                f"角色列表[{i}]", "warning", f"角色 #{i+1} 缺少名称，已跳过"
            ))
            continue

        # 修复 编号
        if not char.编号:
            char.编号 = i + 1
            report.fixes_applied.append(f"角色列表[{i}].编号 → {char.编号}")

        # 修复性别
        if char.性别 not in VALID_GENDERS:
            report.issues.append(ValidationIssue(
                f"角色列表[{i}].性别", "fixed",
                f"性别值无效 '{char.性别}'，已清空"
            ))
            char.性别 = ""

        # 修复角色类型
        if char.角色类型 not in VALID_ROLE_TYPES:
            report.issues.append(ValidationIssue(
                f"角色列表[{i}].角色类型", "fixed",
                f"角色类型无效 '{char.角色类型}'，已清空"
            ))
            char.角色类型 = ""

        # 确保 别名 是列表
        if not isinstance(char.别名, list):
            char.别名 = []

        # 首次出场
        if not char.首次出场:
            char.首次出场 = 1

        valid_characters.append(char)

    script.角色列表 = valid_characters
    script.元信息.角色数量 = len(valid_characters)

    # ── 3. 验证 场景列表 ──
    if not script.场景列表:
        report.is_valid = False
        report.issues.append(ValidationIssue(
            "场景列表", "error", "剧本中没有场景数据"
        ))
        return script, report

    valid_scenes = []
    for i, scene in enumerate(script.场景列表):
        # 修复场景 编号
        if not scene.编号:
            scene.编号 = i + 1
            report.fixes_applied.append(f"场景列表[{i}].编号 → {scene.编号}")

        # 修复场景名
        if not scene.名称:
            scene.名称 = f"场景{scene.编号}"
            report.issues.append(ValidationIssue(
                f"场景列表[{i}].名称", "warning", "场景名缺失，使用默认名"
            ))

        # 确保选项字段存在
        for field in ["地点", "时间", "天气"]:
            if not getattr(scene, field, None):
                setattr(scene, field, "")

        # 场景标题行：确保存在，可自动生成
        if not scene.场景标题行:
            indoor_outdoor = "外景"
            if scene.地点 and any(w in scene.地点 for w in ["室", "房", "厅", "店", "馆", "屋", "内"]):
                indoor_outdoor = "内景"
            time_map = {"清晨": "晨", "早晨": "晨", "白天": "日", "下午": "日", "傍晚": "暮", "夜晚": "夜", "深夜": "夜", "午夜": "夜", "凌晨": "夜"}
            time_short = time_map.get(scene.时间, scene.时间) if scene.时间 else ""
            scene.场景标题行 = f"{indoor_outdoor}. {scene.地点 or '未知'} - {time_short}" if (scene.地点 or time_short) else ""
            if scene.场景标题行:
                report.fixes_applied.append(f"场景列表[{i}].场景标题行 → '{scene.场景标题行}'")

        # 转场：验证合法性
        if scene.转场 and scene.转场 not in VALID_TRANSITIONS:
            report.issues.append(ValidationIssue(
                f"场景列表[{i}].转场", "fixed",
                f"无效转场值 '{scene.转场}'，已清空"
            ))
            scene.转场 = ""

        # 确保 出场角色 是列表
        if not isinstance(scene.出场角色, list):
            scene.出场角色 = []

        # ── 3a. 验证 内容 ──
        valid_acts = []
        for j, act in enumerate(scene.内容):
            # 修复内容 类型
            if act.类型 not in VALID_ACT_TYPES:
                old_type = act.类型
                act.类型 = "动作"
                report.fixes_applied.append(
                    f"场景列表[{i}].内容[{j}].类型: '{old_type}' → '动作'"
                )
                report.issues.append(ValidationIssue(
                    f"场景列表[{i}].内容[{j}].类型", "fixed",
                    f"内容类型无效 '{old_type}'，改为 动作"
                ))

            # 文本为空则跳过
            if not act.文本:
                report.issues.append(ValidationIssue(
                    f"场景列表[{i}].内容[{j}]", "warning", "内容文本为空，已跳过"
                ))
                continue

            # 对白 和 动作 必须有关联角色
            if act.类型 in ("对白", "动作") and not act.角色:
                report.issues.append(ValidationIssue(
                    f"场景列表[{i}].内容[{j}].角色", "warning",
                    f"内容类型为 '{act.类型}' 但缺失角色名"
                ))

            # 情绪 可选，确保存在
            if not act.情绪:
                act.情绪 = ""

            # 备注 可选
            if not act.备注:
                act.备注 = ""

            # ── v2.1 镜头信息验证 ──
            if act.景别 and act.景别 not in VALID_SHOT_SIZES:
                report.issues.append(ValidationIssue(
                    f"场景列表[{i}].内容[{j}].景别", "fixed",
                    f"无效景别值 '{act.景别}'，已清空"
                ))
                act.景别 = ""
            if not act.景别:
                act.景别 = ""

            if act.角度 and act.角度 not in VALID_ANGLES:
                report.issues.append(ValidationIssue(
                    f"场景列表[{i}].内容[{j}].角度", "fixed",
                    f"无效角度值 '{act.角度}'，已清空"
                ))
                act.角度 = ""
            if not act.角度:
                act.角度 = ""

            if act.运动 and act.运动 not in VALID_MOVEMENTS:
                report.issues.append(ValidationIssue(
                    f"场景列表[{i}].内容[{j}].运动", "fixed",
                    f"无效运动值 '{act.运动}'，已清空"
                ))
                act.运动 = ""
            if not act.运动:
                act.运动 = ""

            # ── v2.1 入场/退场标记 ──
            if not act.入场:
                act.入场 = ""
            if not act.退场:
                act.退场 = ""

            valid_acts.append(act)

        scene.内容 = valid_acts
        valid_scenes.append(scene)

    script.场景列表 = valid_scenes
    script.元信息.总场景数 = len(valid_scenes)

    # 最终检查
    if not valid_scenes:
        report.is_valid = False
        report.issues.append(ValidationIssue(
            "场景列表", "error", "没有有效场景数据（所有场景的内容均为空）"
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
