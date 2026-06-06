"""
应用配置管理
从 .env 文件和环境变量加载配置
"""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

# ── 绕过 Windows 系统代理 ──
# Windows 系统代理（127.0.0.1:7890）不可用时会导致所有 HTTPS 请求卡死。
# 设置 NO_PROXY 环境变量强制 httpx / urllib 直连，避免请求超时。
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

# 加载 backend/ 目录下的 .env 文件
load_dotenv(Path(__file__).parent / ".env")

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# JWT 配置
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "720"))  # 默认 30 天（720小时）

# 如果 .env 中没有 JWT_SECRET_KEY，自动生成一个并提示用户
if not JWT_SECRET_KEY:
    _generated = secrets.token_urlsafe(32)
    print(
        f"\n[WARN] JWT_SECRET_KEY 未配置！\n"
        f"请在 backend/.env 中添加以下行：\n"
        f"  JWT_SECRET_KEY={_generated}\n"
        f"然后重启服务。\n"
    )

# 检查 API Key 是否已配置
def is_llm_ready() -> bool:
    """返回 LLM 是否可用（API Key 已配置且不为空）"""
    return bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your-api-key-here")
