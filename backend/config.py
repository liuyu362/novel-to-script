"""
应用配置管理
从 .env 文件和环境变量加载配置
"""
import os
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

# 检查 API Key 是否已配置
def is_llm_ready() -> bool:
    """返回 LLM 是否可用（API Key 已配置且不为空）"""
    return bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your-api-key-here")
