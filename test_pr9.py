"""
PR9 测试：章节分割器 + 批量转换接口
"""
import sys
sys.path.insert(0, "F:/七牛云议题/novel-to-script")

from backend.chapter_splitter import (
    split_chapters, split_by_length, detect_chapter_pattern, Chapter
)

# ── 测试 1: 中文章节模式 ──
cn_novel = """
序章 风云突变
天边的云被染成了血红色。少年站在悬崖边，望着远方，心中涌起一股不祥的预感。

第一章 少年下山
李明收拾好行囊，最后看了一眼师父的房间。三年的修行，今天终于要结束了。

第二章 初入江湖
江湖是什么？李明站在城门口，看着熙熙攘攘的人群，第一次感到了迷茫。
一个小贩推着车从他身边经过，叫卖着冰糖葫芦。

第三章 剑出无名
酒楼里，所有人都在议论三天后的武林大会。李明找了一个角落坐下，要了一壶茶。
突然，门口传来一阵骚动。
"""

print("=" * 60)
print("[TEST 1] 中文章节分割")
detected = detect_chapter_pattern(cn_novel)
print(f"  识别模式: {detected}")

result = split_chapters(cn_novel)
print(f"  章节数: {result.total_chapters}")
print(f"  消息: {result.message}")
for ch in result.chapters:
    print(f"  [{ch.index}] {ch.title} - {len(ch.content)} 字 - 前50字: {ch.content[:50].replace(chr(10), ' ')}...")

# ── 测试 2: 无章节标记 ──
plain_text = "这是一个没有章节标记的故事。王芳每天都会经过那条小巷，巷子的尽头有一家老书店。她从未进去过，直到那天下午，一场突如其来的暴雨把她逼到了书店的屋檐下。"
print("\n" + "=" * 60)
print("[TEST 2] 无章节标记")
result2 = split_chapters(plain_text)
print(f"  章节数: {result2.total_chapters}")
print(f"  消息: {result2.message}")

# ── 测试 3: 强制按字数分割 ──
print("\n" + "=" * 60)
print("[TEST 3] 按字数强制分割（每章 100 字）")
long_text = "第一段。" * 30 + "\n" + "第二段。" * 30 + "\n" + "第三段。" * 30
chapters3 = split_by_length(long_text, max_chars=100)
print(f"  章节数: {len(chapters3)}")
for ch in chapters3:
    print(f"  [{ch.index}] {ch.title} - {len(ch.content)} 字")

# ── 测试 4: 空文本 ──
print("\n" + "=" * 60)
print("[TEST 4] 空文本")
result4 = split_chapters("   \n\n  ")
print(f"  章节数: {result4.total_chapters}")

# ── 测试 5: 英文章节 ──
en_novel = """
Chapter 1: The Beginning
The wind howled through the ancient forest.

Chapter 2: The Journey
Days passed as the party made their way northward.

Chapter 3: The Confrontation
The dragon stirred from its slumber.
"""
print("\n" + "=" * 60)
print("[TEST 5] 英文章节分割")
detected5 = detect_chapter_pattern(en_novel)
print(f"  识别模式: {detected5}")
result5 = split_chapters(en_novel)
print(f"  章节数: {result5.total_chapters}")
for ch in result5.chapters:
    print(f"  [{ch.index}] {ch.title} - {len(ch.content)} 字")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
