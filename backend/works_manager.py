"""
作品管理模块 — SQLite 数据库操作

表结构：
  works:
    id              INTEGER PRIMARY KEY AUTOINCREMENT
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


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ======================== 初始化 ========================

def init_db() -> None:
    """创建数据库和表（幂等）"""
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS works (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL DEFAULT '',
            original_text   TEXT    NOT NULL DEFAULT '',
            analysis_data   TEXT    DEFAULT '{}',
            script_data     TEXT    DEFAULT '{}',
            logic_data      TEXT    DEFAULT '{}',
            current_step    INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ======================== CRUD ========================

def create_work(title: str = "", text: str = "") -> int:
    """新建作品，返回 id"""
    conn = _connect()
    now = _now()
    cur = conn.execute(
        "INSERT INTO works (title, original_text, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title, text, now, now),
    )
    conn.commit()
    work_id = cur.lastrowid
    conn.close()
    return work_id


def list_works() -> list[dict]:
    """作品列表（仅摘要，不含全文/分析数据）"""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, current_step, created_at, updated_at FROM works ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_work(work_id: int) -> dict | None:
    """获取作品完整数据"""
    conn = _connect()
    row = conn.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def update_work(work_id: int, **kwargs) -> bool:
    """更新作品字段（id 不可改）

    支持的字段：
        title, original_text, analysis_data, script_data,
        logic_data, current_step
    """
    allowed = {"title", "original_text", "analysis_data",
               "script_data", "logic_data", "current_step"}
    updates = {}
    for k, v in kwargs.items():
        if k in allowed:
            if k.endswith("_data") and isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            updates[k] = v

    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    set_clause += ", updated_at = ?"
    values.append(_now())

    conn = _connect()
    cur = conn.execute(
        f"UPDATE works SET {set_clause} WHERE id = ?",
        [*values, work_id],
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def delete_work(work_id: int) -> bool:
    """删除作品"""
    conn = _connect()
    cur = conn.execute("DELETE FROM works WHERE id = ?", (work_id,))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


# ======================== 辅助 ========================

def _row_to_dict(row: sqlite3.Row) -> dict:
    """将数据库行转为字典，JSON 字段自动解析"""
    d = dict(row)
    for key in ("analysis_data", "script_data", "logic_data"):
        try:
            d[key] = json.loads(d[key]) if d[key] else {}
        except (json.JSONDecodeError, TypeError):
            d[key] = {}
    return d


# ======================== 自动初始化 ========================

init_db()
