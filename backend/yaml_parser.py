"""
YAML 解析器（全中文字段名）
将 LLM 输出的 YAML 文本解析为 Script 结构化对象
支持容错：处理 LLM 输出的常见格式问题
"""
import re
import yaml
from typing import Optional

from backend.schema import Script, Meta, Character, Scene, Act
from backend.errors import AppException, ErrorCode


def _clean_llm_output(raw: str) -> str:
    """清洗 LLM 输出中的常见噪音"""
    # 去掉 markdown 代码块标记
    text = raw.strip()
    if text.startswith("```"):
        # 找到第一行换行后才是真正的 YAML
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()

    # 去掉 LLM 有时在开头加的注释/说明
    lines = text.split("\n")
    # 找到第一个非空、非注释、以缩进或 "元信息" / "角色列表" / "场景列表" 开头的行
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("元信息:", "角色列表:", "场景列表:")):
            start_idx = i
            break
    text = "\n".join(lines[start_idx:])

    return text.strip()


def _parse_yaml(text: str) -> dict:
    """安全解析 YAML，失败时尝试修复后重试"""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        pass

    # 尝试修复：去掉每行末尾的逗号（LLM 常见错误）
    fixed = re.sub(r",\s*$", "", text, flags=re.MULTILINE)
    try:
        return yaml.safe_load(fixed)
    except yaml.YAMLError:
        pass

    raise AppException(ErrorCode.YAML_INVALID, "LLM 输出的 YAML 格式无法解析，请重试")


def _dict_to_character(data: dict) -> Character:
    """字典 → Character 对象"""
    return Character(
        编号=data.get("编号", 0),
        姓名=data.get("姓名", "未知"),
        别名=data.get("别名", []),
        性别=data.get("性别", ""),
        年龄=data.get("年龄", ""),
        角色类型=data.get("角色类型", ""),
        描述=data.get("描述", ""),
        首次出场=data.get("首次出场", 0),
    )


def _dict_to_act(data: dict) -> Act:
    """字典 → Act 对象"""
    return Act(
        类型=data.get("类型", "动作"),
        文本=data.get("文本", ""),
        角色=data.get("角色", ""),
        情绪=data.get("情绪", ""),
        备注=data.get("备注", ""),
        景别=data.get("景别", ""),
        角度=data.get("角度", ""),
        运动=data.get("运动", ""),
        入场=data.get("入场", ""),
        退场=data.get("退场", ""),
    )


def _dict_to_scene(data: dict) -> Scene:
    """字典 → Scene 对象"""
    return Scene(
        编号=data.get("编号", 0),
        名称=data.get("名称", "未命名场景"),
        地点=data.get("地点", ""),
        时间=data.get("时间", ""),
        天气=data.get("天气", ""),
        出场角色=data.get("出场角色", []),
        内容=[_dict_to_act(a) for a in data.get("内容", [])],
        场景标题行=data.get("场景标题行", ""),
        转场=data.get("转场", ""),
    )


def parse_yaml_to_script(raw_output: str, source_title: str = "") -> Script:
    """将 LLM 输出的 YAML 文本解析为 Script 对象

    Args:
        raw_output: LLM 原始输出文本
        source_title: 原作标题

    Returns:
        Script: 结构化的剧本对象

    Raises:
        AppException: YAML 格式错误
    """
    cleaned = _clean_llm_output(raw_output)
    data = _parse_yaml(cleaned)

    if not isinstance(data, dict):
        raise AppException(ErrorCode.YAML_INVALID, "YAML 解析结果不是字典结构")

    # 解析 元信息
    meta_dict = data.get("元信息", {})
    meta = Meta(
        标题=meta_dict.get("标题", f"{source_title}·剧本"),
        原著作=source_title or meta_dict.get("原著作", ""),
        版本=meta_dict.get("版本", "电影版"),
        总场景数=meta_dict.get("总场景数", 0),
        角色数量=meta_dict.get("角色数量", 0),
    )

    # 解析 角色列表
    characters = [
        _dict_to_character(c) for c in data.get("角色列表", [])
    ]

    # 解析 场景列表
    scenes = [
        _dict_to_scene(s) for s in data.get("场景列表", [])
    ]

    script = Script(元信息=meta, 角色列表=characters, 场景列表=scenes)

    # 校验：至少有一个场景
    if not script.场景列表:
        raise AppException(ErrorCode.YAML_INVALID, "剧本中没有有效场景数据")

    return script


def script_to_yaml(script: Script) -> str:
    """Script 对象序列化为 YAML 字符串"""
    # 去掉 None 值的字段，让输出更干净
    def _filter_none(d):
        if isinstance(d, dict):
            return {k: _filter_none(v) for k, v in d.items() if v is not None}
        elif isinstance(d, list):
            return [_filter_none(i) for i in d]
        return d

    clean_dict = _filter_none(script.to_dict())
    return yaml.dump(
        clean_dict,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
