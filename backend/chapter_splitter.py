"""
Chapter Splitter — 智能章节分割
支持中文小说常见章节格式的自动识别与切割
"""
import re
from dataclasses import dataclass, field
from typing import Optional


# ── 章节匹配模式 ─────────────────────────────────────────
CHAPTER_PATTERNS: list[tuple[str, str]] = [
    # (正则, 模式名称)
    # ^\s* 允许行首有空格/制表符，兼容常见小说排版
    (r'^\s*第[零一二三四五六七八九十百千\d]+章[^\n]*', "中文章节"),
    (r'^\s*第[零一二三四五六七八九十百千\d]+节[^\n]*', "中文小节"),
    (r'^\s*Chapter\s+\d+[^\n]*', "英文章节"),
    (r'^\s*[Vv]olume\s+\d+[^\n]*', "英文卷"),
    (r'^\s*第[零一二三四五六七八九十百千\d]+卷[^\n]*', "中文卷"),
    (r'^\s*[Cc]h\.?\s*\d+[^\n]*', "缩写章节"),
    (r'^\s*(序章|楔子|终章|尾声|番外|后记|前言)[^\n]*', "特殊章节"),
    (r'^\s*[（(][零一二三四五六七八九十百千\d]+[)）][^\n]*', "括号序号"),
]

# 按中文章节序号排序
CN_NUM_MAP: dict[str, int] = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "百": 100, "千": 1000,
}

SPECIAL_CHAPTER_ORDER: dict[str, int] = {
    "序章": -10, "楔子": -9, "前言": -8,
    "终章": 9999, "尾声": 99998, "后记": 99999, "番外": 99990,
}


@dataclass
class Chapter:
    """分割后的章节"""
    index: int               # 序号（从 1 开始）
    title: str               # 章节标题（如"第三章 初入江湖"）
    content: str             # 章节正文
    start_pos: int           # 原文中的起始位置
    end_pos: int             # 原文中的结束位置
    pattern_name: str = ""   # 匹配到的模式名称


@dataclass
class SplitResult:
    """分割结果"""
    total_chapters: int
    pattern_used: str         # 识别的章节模式
    chapters: list[Chapter]
    prelude: str = ""         # 第一个章节之前的文本（如果没有模式匹配，则是全文）
    message: str = ""


def _cn_num_to_int(s: str) -> int:
    """中文数字 → int（支持百/千/十）"""
    total = 0
    unit = 1
    for ch in reversed(s):
        if ch in CN_NUM_MAP:
            val = CN_NUM_MAP[ch]
            if val >= 10:
                unit = max(unit, val)
            else:
                total += val * (unit if unit > 1 else 1)
        else:
            try:
                total += int(ch) * (unit if unit > 1 else 1)
            except ValueError:
                pass
    return total or 1


def _extract_chapter_index(title: str, pattern_name: str) -> int:
    """从章节标题中提取序号"""
    if pattern_name == "特殊章节":
        for key, idx in SPECIAL_CHAPTER_ORDER.items():
            if key in title:
                return idx
        return 0

    # 中文数字
    cn_match = re.search(r'[零一二三四五六七八九十百千]+', title)
    if cn_match:
        return _cn_num_to_int(cn_match.group())

    # 阿拉伯数字
    num_match = re.search(r'(\d+)', title)
    if num_match:
        return int(num_match.group(1))

    return 0


def detect_chapter_pattern(text: str) -> str:
    """自动检测文本使用的章节格式

    返回模式名称（如 "中文章节"），若无法识别返回 ""
    """
    lines = text.strip().split("\n")
    scores: dict[str, int] = {}

    for line in lines[:200]:  # 只扫描前 200 行
        line = line.strip()
        for pattern, name in CHAPTER_PATTERNS:
            if re.match(pattern, line):
                scores[name] = scores.get(name, 0) + 1

    if not scores:
        return ""

    return max(scores, key=scores.get)


def split_chapters(text: str, pattern_override: str = "") -> SplitResult:
    """将小说文本按章节分割

    Args:
        text: 小说全文
        pattern_override: 强制指定章节模式（如 "中文章节"），空字符串则自动检测

    Returns:
        SplitResult: 包含所有章节的分割结果
    """
    if not text.strip():
        return SplitResult(
            total_chapters=0,
            pattern_used="",
            chapters=[],
            message="文本为空",
        )

    # 确定使用的模式
    if pattern_override:
        active_pattern = pattern_override
    else:
        active_pattern = detect_chapter_pattern(text)

    # 构建匹配正则
    if active_pattern:
        for ptn, name in CHAPTER_PATTERNS:
            if name == active_pattern:
                chapter_regex = re.compile(ptn, re.MULTILINE)
                break
        else:
            chapter_regex = re.compile(CHAPTER_PATTERNS[0][0], re.MULTILINE)
    else:
        # 无章节标记 → 整个文本作为一个章节
        return SplitResult(
            total_chapters=1,
            pattern_used="无章节标记，整体作为一个章节",
            chapters=[Chapter(
                index=1,
                title="全文",
                content=text.strip(),
                start_pos=0,
                end_pos=len(text),
                pattern_name="无标记",
            )],
            message="未检测到章节标记，整体作为单个章节处理",
        )

    # 查找所有章节标题位置
    matches = list(chapter_regex.finditer(text))

    if not matches:
        return SplitResult(
            total_chapters=1,
            pattern_used=active_pattern,
            chapters=[Chapter(
                index=1,
                title="全文",
                content=text.strip(),
                start_pos=0,
                end_pos=len(text),
                pattern_name=active_pattern,
            )],
            message=f"未匹配到章节标题（模式: {active_pattern}），整体作为单个章节",
        )

    chapters: list[Chapter] = []
    prelude = ""

    # 第一个章节标题之前的文本作为引子
    if matches[0].start() > 0:
        prelude = text[:matches[0].start()].strip()

    for i, m in enumerate(matches):
        title = m.group().strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        raw_index = _extract_chapter_index(title, active_pattern)

        chapters.append(Chapter(
            index=i + 1,
            title=title,
            content=text[start:end].strip(),
            start_pos=start,
            end_pos=end,
            pattern_name=active_pattern,
        ))

    # 重排序号（处理序章/终章等特殊序号）
    chapters.sort(key=lambda c: _extract_chapter_index(c.title, active_pattern))
    for new_idx, ch in enumerate(chapters, 1):
        ch.index = new_idx

    return SplitResult(
        total_chapters=len(chapters),
        pattern_used=active_pattern,
        chapters=chapters,
        prelude=prelude,
        message=f"成功分割为 {len(chapters)} 个章节",
    )


def split_by_length(text: str, max_chars: int = 5000) -> list[Chapter]:
    """按字数强制分割（兜底方案，用于无章节标记的文本）

    Args:
        text: 小说全文
        max_chars: 每章最大字数

    Returns:
        list[Chapter]: 分割后的章节列表
    """
    if len(text) <= max_chars:
        return [Chapter(
            index=1, title="全文", content=text.strip(),
            start_pos=0, end_pos=len(text), pattern_name="字数分割",
        )]

    chapters: list[Chapter] = []
    paragraphs = text.split("\n")
    current = ""
    idx = 0

    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            idx += 1
            chapters.append(Chapter(
                index=idx,
                title=f"第{idx}部分",
                content=current.strip(),
                start_pos=0,
                end_pos=0,
                pattern_name="字数分割",
            ))
            current = ""

        current += para + "\n"

    if current.strip():
        idx += 1
        chapters.append(Chapter(
            index=idx,
            title=f"第{idx}部分",
            content=current.strip(),
            start_pos=0,
            end_pos=0,
            pattern_name="字数分割",
        ))

    return chapters
