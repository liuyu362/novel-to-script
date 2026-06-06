"""
用户管理模块
users 表：id / nickname / password_hash / created_at
注册 / 登录 / token 验证
"""

import sqlite3
import hashlib
import time
import json
from pathlib import Path
from fastapi import HTTPException

DB_PATH = Path(__file__).parent / "works.db"

# ── 初始化 users 表 ────────────────────────────────────────────────────────

def init_users_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname       TEXT    UNIQUE NOT NULL,
                password_hash  TEXT    NOT NULL,
                created_at     TEXT    DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()


# ── 密码处理 ────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    return _hash_password(password) == password_hash


# ── 注册 ──────────────────────────────────────────────────────────────────────

def register_user(nickname: str, password: str) -> dict:
    """
    注册新用户。
    返回 {"id": ..., "nickname": ..., "token": ...}
    昵称重复时抛出 ValueError。
    """
    password_hash = _hash_password(password)
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (nickname, password_hash, created_at) VALUES (?, ?, ?)",
                (nickname, password_hash, now),
            )
            user_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"昵称「{nickname}」已被使用，请换一个")

    token = _generate_token(user_id)
    return {
        "id": user_id,
        "nickname": nickname,
        "token": token,
    }


# ── 登录 ──────────────────────────────────────────────────────────────────────

def login_user(nickname: str, password: str) -> dict:
    """
    登录用户。
    返回 {"id": ..., "nickname": ..., "token": ...}
    昵称不存在或密码错误时抛出 ValueError。
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, nickname, password_hash FROM users WHERE nickname = ?",
            (nickname,),
        ).fetchone()

    if not row:
        raise ValueError("昵称不存在")
    if not _verify_password(password, row[2]):
        raise ValueError("密码错误")

    token = _generate_token(row[0])
    return {
        "id": row[0],
        "nickname": row[1],
        "token": token,
    }


# ── Token 生成与验证 ──────────────────────────────────────────────────────────

def _generate_token(user_id: int) -> str:
    """简单 token：user_<id>_<timestamp>，不 JWT，够用"""
    return f"user_{user_id}_{int(time.time())}"


def parse_token(token: str) -> int:
    """
    从 token 解析 user_id。
    返回 user_id（int）。
    token 格式非法时抛出 ValueError。
    """
    if not token or not token.startswith("user_"):
        raise ValueError("token 格式非法")
    try:
        parts = token.split("_")
        user_id = int(parts[1])
        return user_id
    except (IndexError, ValueError):
        raise ValueError("token 格式非法")


def get_current_user(request) -> int:
    """
    从 FastAPI request 的 Authorization header 解析当前用户。
    返回 user_id（int）。
    无 token / token 非法时抛出 HTTP 401。
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    token = auth[len("Bearer "):].strip()
    try:
        return parse_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="token 无效或已过期，请重新登录")


# ── 用户是否存在（供外部校验） ──────────────────────────────────────────────

def user_exists(user_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row is not None
