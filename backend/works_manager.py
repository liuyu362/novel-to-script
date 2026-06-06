"""
作品管理模块 — SQLite 数据库操作（多用户版）

表结构：
  works:
    id              INTEGER PRIMARY KEY AUTOINCREMENT
    user_id         INTEGER REFERENCES users(id)  — 所属用户
    title           TEXT    作品标题
    original_text   TEXT    小说原文
    analysis_data   TEXT    综合解读结果 JSON（对应 localStorage novelAnalysis）
    script_data     TEXT    剧本生成结果 JSON（对应 localStorage novelScript）
    logic_data      TEXT    逻辑检测结果 JSON（对应 localStorage novelLogic）
    current_step    INTEGER 当前所处步骤 (1=解读, 2=管理, 3=改编, 4=检测, 5=导出)
    created_at      TEXT    创建时间
    updated_at      TEXT    最后修改时间
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "works.db")


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（自动创建表）"""
    need_init = not os.path.isfile(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if need_init:
        _init_db(conn)
    # 即使文件已存在（如 users 表先创建），也检查 works 表是否存在
    else:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='works'"
        ).fetchone()
        if not row:
            _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection):
    """初始化数据库表结构"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS works (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER DEFAULT NULL REFERENCES users(id),
            title           TEXT    NOT NULL DEFAULT '未命名作品',
            original_text   TEXT    DEFAULT '',
            analysis_data   TEXT    DEFAULT NULL,
            script_data     TEXT    DEFAULT NULL,
            logic_data      TEXT    DEFAULT NULL,
            current_step    INTEGER DEFAULT 1,
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        )
    """)
    conn.commit()


def _now() -> str:
    """当前时间字符串（ISO 8601）"""
    return datetime.now().isoformat(sep=" ", timespec="seconds")


# ── CRUD 操作（全部带 user_id） ────────────────────────────────────

def create_work(title: str, text: str, user_id: int) -> int:
    """新建作品，绑定 user_id，返回新作品 ID"""
    now = _now()
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO works
               (user_id, title, original_text, current_step, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (user_id, title or "未命名作品", text, now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_works(user_id: int) -> list[dict]:
    """作品列表（摘要，仅当前用户）"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, title, current_step,
                      LENGTH(original_text) AS text_length,
                      created_at, updated_at
               FROM works
               WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,),
        ).fetchall()
        return [_row_to_summary(r) for r in rows]
    finally:
        conn.close()


def get_work(work_id: int, user_id: int) -> dict | None:
    """读取单部作品完整数据（校验归属）"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM works WHERE id = ? AND user_id = ?",
            (work_id, user_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_work(work_id: int, user_id: int, **kwargs) -> bool:
    """更新作品字段（校验归属，支持部分更新）

    kwargs 允许的键：
        title / original_text / analysis_data / script_data /
        logic_data / current_step
    """
    allowed = {
        "title", "original_text", "analysis_data",
        "script_data", "logic_data", "current_step",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return True  # 无变更，视为成功

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    values.append(_now())    # updated_at
    values.append(work_id)
    values.append(user_id)

    conn = _get_conn()
    try:
        cur = conn.execute(
            f"UPDATE works SET {sets}, updated_at = ? WHERE id = ? AND user_id = ?",
            values,
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_work(work_id: int, user_id: int) -> bool:
    """删除作品（校验归属），返回是否成功"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM works WHERE id = ? AND user_id = ?",
            (work_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── 辅助函数 ──────────────────────────────────────────────────

def _row_to_summary(row: sqlite3.Row) -> dict:
    """将数据库行转为列表摘要（不含大字段）"""
    return {
        "id":            row["id"],
        "title":          row["title"],
        "current_step":   row["current_step"],
        "text_length":    row["text_length"],
        "created_at":     row["created_at"],
        "updated_at":     row["updated_at"],
    }
