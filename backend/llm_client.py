"""
DeepSeek API 客户端封装
统一错误处理，抛出 AppException
"""
from openai import OpenAI
from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, is_llm_ready
from backend.errors import AppException, ErrorCode


def get_client() -> "OpenAI | None":
    """获取 DeepSeek API 客户端实例，未配置 Key 时返回 None"""
    if not is_llm_ready():
        return None
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    调用 DeepSeek 大模型

    Args:
        system_prompt: 系统提示词（设定角色和任务）
        user_prompt: 用户输入内容

    Returns:
        模型生成的文本

    Raises:
        AppException: 各种可预期错误，携带错误码
    """
    client = get_client()
    if client is None:
        raise AppException(
            ErrorCode.LLM_NOT_READY,
            "DeepSeek API Key 未配置。请检查 backend/.env 文件"
        )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=16384,
            timeout=180,
        )
        return response.choices[0].message.content

    except RateLimitError:
        raise AppException(ErrorCode.LLM_RATE_LIMIT)
    except APITimeoutError:
        raise AppException(ErrorCode.LLM_TIMEOUT)
    except (APIConnectionError, InternalServerError):
        raise AppException(ErrorCode.LLM_CALL_FAILED, "AI 服务连接异常，请稍后重试")
    except Exception as e:
        # 兜底：其他未知错误
        raise AppException(ErrorCode.LLM_CALL_FAILED, f"AI 调用失败：{str(e)[:100]}")
