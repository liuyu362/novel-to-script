"""
用户管理模块
users 表：id / nickname / password_hash / created_at
注册 / 登录 / JWT 签发与验证
"""

import sqlite3
import hashlib
import json
import datetime
from pathlib import Path
from fastapi import HTTPException

import jwt
from backend.config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_HOURS

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


# ── 密码处理（升级为 bcrypt 预留接口，当前仍用 SHA256） ──────────────

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    return _hash_password(password) == password_hash


# ── JWT 签发与验证 ─────────────────────────────────────────────────────────

def create_jwt_token(user_id: int, nickname: str) -> str:
    """
    签发 JWT token，payload 包含：
      - user_id:  用户 ID
      - nickname:  用户昵称
      - exp:       过期时间（当前时间 + JWT_EXPIRE_HOURS）
    返回字符串 token。
    """
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY 未配置，请在 .env 中设置")
    payload = {
        "user_id": user_id,
        "nickname": nickname,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_jwt_token(token: str) -> int:
    """
    验证 JWT token，返回 user_id（int）。
    token 过期、签名无效、格式错误均抛出 ValueError。
    """
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY 未配置")
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise ValueError("token 中缺少 user_id")
        return int(user_id)
    except jwt.ExpiredSignatureError:
        raise ValueError("token 已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise ValueError("token 无效或已被篡改")


# ── 注册 ──────────────────────────────────────────────────────────────────────

def register_user(nickname: str, password: str) -> dict:
    """
    注册新用户。
    返回 {"id": ..., "nickname": ..., "token": ...}
    昵称重复时抛出 ValueError。
    """
    password_hash = _hash_password(password)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    token = create_jwt_token(user_id, nickname)
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

    token = create_jwt_token(row[0], row[1])
    return {
        "id": row[0],
        "nickname": row[1],
        "token": token,
    }


# ── FastAPI 依赖：获取当前登录用户 ─────────────────────────────────────────

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
        return verify_jwt_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ── 用户是否存在（供外部校验） ──────────────────────────────────────────────

def user_exists(user_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row is not None
